"""
ATOM Zendesk Integration Service - Enhanced Version
Comprehensive Zendesk API integration for customer support and ticketing management
Following ATOM integration patterns for consistency and reliability
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import aiohttp
import logging
from loguru import logger
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, User, Organization

@dataclass
class ZendeskConfig:
    """Zendesk configuration class"""
    subdomain: str
    email: str
    token: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: List[str] = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["tickets:read", "tickets:write", "users:read", "organizations:read"]
        if not self.subdomain.startswith('http'):
            self.api_base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

class ZendeskService:
    """Enhanced Zendesk service class for API interactions"""
    
    def __init__(self, config: Optional[ZendeskConfig] = None):
        self.config = config or self._get_config_from_env()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.max_retries = 3
        self._zenpy_client: Optional[Zenpy] = None
        
    def _get_config_from_env(self) -> ZendeskConfig:
        """Load configuration from environment variables"""
        return ZendeskConfig(
            subdomain=os.getenv("ZENDESK_SUBDOMAIN", ""),
            email=os.getenv("ZENDESK_EMAIL", ""),
            token=os.getenv("ZENDESK_TOKEN", ""),
            client_id=os.getenv("ZENDESK_CLIENT_ID"),
            client_secret=os.getenv("ZENDESK_CLIENT_SECRET"),
            redirect_uri=os.getenv("ZENDESK_REDIRECT_URI"),
            scopes=os.getenv("ZENDESK_SCOPES", "tickets:read tickets:write users:read organizations:read").split()
        )
    
    def _get_zenpy_client(self) -> Optional[Zenpy]:
        """Get or create Zenpy client"""
        if not self._zenpy_client:
            if not all([self.config.subdomain, self.config.email, self.config.token]):
                logger.error("Zendesk credentials are not configured")
                return None
                
            creds = {
                'subdomain': self.config.subdomain,
                'email': self.config.email,
                'token': self.config.token
            }
            
            try:
                self._zenpy_client = Zenpy(**creds)
                logger.info(f"Zendesk client created for {self.config.subdomain}")
            except Exception as e:
                logger.error(f"Failed to create Zendesk client: {e}")
                return None
                
        return self._zenpy_client
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for REST API calls"""
        if not self.session or self.session.closed:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ATOM-Integration/1.0"
            }
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout
            )
        return self.session
    
    async def _make_rest_request(
        self, 
        method: str, 
        endpoint: str, 
        access_token: str,
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated REST request to Zendesk API with retry logic"""
        session = await self._get_session()
        url = f"{self.config.api_base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers
                ) as response:
                    if response.status == 401:
                        raise Exception("Invalid or expired access token")
                    elif response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 5))
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Zendesk API error: {response.status} - {error_text}")
                    
                    if response.status == 204:  # No Content
                        return {"success": True}
                    
                    return await response.json()
                    
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Request failed after {self.max_retries} attempts: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        
        raise Exception("Request failed after all retries")

# Legacy functions for backward compatibility
async def get_zendesk_client(user_id: str, db_conn_pool) -> Optional[Zenpy]:
    """Legacy function - use ZendeskService instead"""
    subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
    email = os.environ.get("ZENDESK_EMAIL")
    token = os.environ.get("ZENDESK_TOKEN")

    if not all([subdomain, email, token]):
        logger.error("Zendesk credentials are not configured in environment variables.")
        return None

    creds = {
        'email': email,
        'token': token,
        'subdomain': subdomain
    }

    try:
        client = Zenpy(**creds)
        return client
    except Exception as e:
        logger.error(f"Failed to create Zendesk client: {e}", exc_info=True)
        return None

async def create_ticket(client: Zenpy, ticket_data: Dict[str, Any]) -> Ticket:
    """Legacy function - use ZendeskService.create_ticket instead"""
    ticket_audit = client.tickets.create(Ticket(**ticket_data))
    return ticket_audit.ticket

async def get_ticket(client: Zenpy, ticket_id: str) -> Ticket:
    """Legacy function - use ZendeskService.get_ticket instead"""
    ticket = client.tickets(id=ticket_id)
    return ticket

async def create_user(client: Zenpy, name: str, email: str) -> User:
    """Legacy function - use ZendeskService.create_user instead"""
    user = client.users.create(User(name=name, email=email))
    return user.user

# Enhanced service methods for ZendeskService
class ZendeskServiceEnhanced(ZendeskService):
    """Enhanced Zendesk service with comprehensive API methods"""
    
    async def get_tickets(
        self, 
        access_token: Optional[str] = None,
        limit: int = 30,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned: bool = False
    ) -> Dict[str, Any]:
        """Get list of tickets with optional filtering"""
        if access_token:
            # Use REST API
            params = {"per_page": min(limit, 100)}
            
            if status:
                params["status"] = status
            if priority:
                params["priority"] = priority
            if assigned:
                params["assigned"] = "true"
            
            return await self._make_rest_request("GET", "/tickets.json", access_token, params=params)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            tickets = list(client.tickets())
            
            # Apply filters
            if status:
                tickets = [t for t in tickets if t.status == status]
            if priority:
                tickets = [t for t in tickets if t.priority == priority]
            if assigned:
                tickets = [t for t in tickets if t.assignee_id is not None]
            
            return {"tickets": tickets[:limit]}
    
    async def get_ticket(self, ticket_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Get specific ticket by ID with comments"""
        if access_token:
            return await self._make_rest_request("GET", f"/tickets/{ticket_id}.json", access_token)
        else:
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            ticket = client.tickets(id=ticket_id)
            return {"ticket": ticket}
    
    async def create_ticket(
        self, 
        access_token: Optional[str] = None,
        subject: str = "",
        comment: str = "",
        priority: Optional[str] = None,
        assignee_id: Optional[int] = None,
        requester_email: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new support ticket"""
        if access_token:
            # Use REST API
            ticket_data = {
                "ticket": {
                    "subject": subject,
                    "comment": {"body": comment}
                }
            }
            
            if priority:
                ticket_data["ticket"]["priority"] = priority
            if assignee_id:
                ticket_data["ticket"]["assignee_id"] = assignee_id
            if requester_email:
                ticket_data["ticket"]["requester"] = {"email": requester_email}
            if tags:
                ticket_data["ticket"]["tags"] = tags
            
            return await self._make_rest_request("POST", "/tickets.json", access_token, data=ticket_data)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            ticket_dict = {
                "subject": subject,
                "description": comment
            }
            
            if priority:
                ticket_dict["priority"] = priority
            if assignee_id:
                ticket_dict["assignee_id"] = assignee_id
            if requester_email:
                ticket_dict["requester"] = {"email": requester_email}
            if tags:
                ticket_dict["tags"] = tags
            
            ticket = Ticket(**ticket_dict)
            result = client.tickets.create(ticket)
            
            return {"ticket": result.ticket}
    
    async def update_ticket(
        self, 
        ticket_id: int,
        access_token: Optional[str] = None,
        comment: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update existing ticket"""
        if access_token:
            # Use REST API
            ticket_data = {"ticket": {}}
            
            if comment:
                ticket_data["ticket"]["comment"] = {"body": comment}
            if status:
                ticket_data["ticket"]["status"] = status
            if priority:
                ticket_data["ticket"]["priority"] = priority
            if assignee_id:
                ticket_data["ticket"]["assignee_id"] = assignee_id
            
            return await self._make_rest_request("PUT", f"/tickets/{ticket_id}.json", access_token, data=ticket_data)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            ticket = client.tickets(id=ticket_id)
            
            if comment:
                ticket.comment = comment
            if status:
                ticket.status = status
            if priority:
                ticket.priority = priority
            if assignee_id:
                ticket.assignee_id = assignee_id
            
            result = client.tickets.update(ticket)
            return {"ticket": result.ticket}
    
    async def get_users(
        self, 
        access_token: Optional[str] = None,
        limit: int = 30,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get list of users with optional role filtering"""
        if access_token:
            # Use REST API
            params = {"per_page": min(limit, 100)}
            
            if role:
                params["role"] = role
            
            return await self._make_rest_request("GET", "/users.json", access_token, params=params)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            users = list(client.users())
            
            if role:
                users = [u for u in users if u.role == role]
            
            return {"users": users[:limit]}
    
    async def get_user(self, user_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Get specific user by ID"""
        if access_token:
            return await self._make_rest_request("GET", f"/users/{user_id}.json", access_token)
        else:
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            user = client.users(id=user_id)
            return {"user": user}
    
    async def create_user(
        self,
        access_token: Optional[str] = None,
        name: str = "",
        email: str = "",
        phone: Optional[str] = None,
        organization_id: Optional[int] = None,
        role: str = "end-user"
    ) -> Dict[str, Any]:
        """Create a new user"""
        if access_token:
            # Use REST API
            user_data = {"user": {"name": name, "email": email, "role": role}}
            
            if phone:
                user_data["user"]["phone"] = phone
            if organization_id:
                user_data["user"]["organization_id"] = organization_id
            
            return await self._make_rest_request("POST", "/users.json", access_token, data=user_data)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            user_dict = {"name": name, "email": email, "role": role}
            
            if phone:
                user_dict["phone"] = phone
            if organization_id:
                user_dict["organization_id"] = organization_id
            
            user = User(**user_dict)
            result = client.users.create(user)
            
            return {"user": result.user}
    
    async def get_organizations(
        self, 
        access_token: Optional[str] = None,
        limit: int = 30
    ) -> Dict[str, Any]:
        """Get list of organizations"""
        if access_token:
            # Use REST API
            params = {"per_page": min(limit, 100)}
            return await self._make_rest_request("GET", "/organizations.json", access_token, params=params)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            organizations = list(client.organizations())
            return {"organizations": organizations[:limit]}
    
    async def get_organization(self, org_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Get specific organization by ID"""
        if access_token:
            return await self._make_rest_request("GET", f"/organizations/{org_id}.json", access_token)
        else:
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            organization = client.organizations(id=org_id)
            return {"organization": organization}
    
    async def search_tickets(
        self, 
        access_token: Optional[str] = None,
        query: str = "",
        limit: int = 30
    ) -> Dict[str, Any]:
        """Search tickets by query"""
        if access_token:
            # Use REST API
            params = {
                "query": query,
                "per_page": min(limit, 100)
            }
            return await self._make_rest_request("GET", "/search.json", access_token, params=params)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            # Search for tickets
            results = client.search(query, type='ticket')
            tickets = list(results)
            
            return {"tickets": tickets[:limit], "count": len(tickets)}
    
    async def get_ticket_metrics(
        self, 
        access_token: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get ticket metrics and analytics"""
        if access_token:
            # Use REST API
            params = {}
            
            if start_date:
                params["start_date"] = start_date.strftime("%Y-%m-%d")
            if end_date:
                params["end_date"] = end_date.strftime("%Y-%m-%d")
            
            return await self._make_rest_request("GET", "/tickets/metrics.json", access_token, params=params)
        else:
            # For Zenpy, we'll return basic metrics
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            tickets = list(client.tickets())
            
            # Basic metrics calculation
            total_tickets = len(tickets)
            open_tickets = len([t for t in tickets if t.status in ['new', 'open']])
            solved_tickets = len([t for t in tickets if t.status == 'solved'])
            
            return {
                "metrics": {
                    "total_tickets": total_tickets,
                    "open_tickets": open_tickets,
                    "solved_tickets": solved_tickets,
                    "resolution_rate": (solved_tickets / total_tickets * 100) if total_tickets > 0 else 0
                }
            }
    
    async def add_comment_to_ticket(
        self, 
        ticket_id: int,
        access_token: Optional[str] = None,
        comment: str = "",
        public: bool = True,
        author_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add comment to existing ticket"""
        if access_token:
            # Use REST API
            comment_data = {
                "comment": {
                    "body": comment,
                    "public": public
                }
            }
            
            if author_id:
                comment_data["comment"]["author_id"] = author_id
            
            return await self._make_rest_request("PUT", f"/tickets/{ticket_id}.json", access_token, data=comment_data)
        else:
            # Use Zenpy client
            client = self._get_zenpy_client()
            if not client:
                raise Exception("Unable to create Zendesk client")
            
            ticket = client.tickets(id=ticket_id)
            ticket.comment = comment
            
            result = client.tickets.update(ticket)
            return {"ticket": result.ticket}
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
        self._zenpy_client = None

# Utility functions for response formatting
def format_zendesk_response(data: Any, service: str = "zendesk") -> Dict[str, Any]:
    """Format successful Zendesk response"""
    return {
        "ok": True,
        "data": data,
        "service": service,
        "timestamp": datetime.utcnow().isoformat()
    }

def format_zendesk_error_response(error_msg: str, service: str = "zendesk") -> Dict[str, Any]:
    """Format error response"""
    return {
        "ok": False,
        "error": {
            "code": "ZENDESK_ERROR",
            "message": error_msg,
            "service": service
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Zendesk service factory
def create_zendesk_service(config: Optional[ZendeskConfig] = None) -> ZendeskServiceEnhanced:
    """Factory function to create enhanced Zendesk service instance"""
    return ZendeskServiceEnhanced(config)
