import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# HubSpot API configuration
HUBSPOT_API_BASE = "https://api.hubapi.com"

class HubSpotService:
    """Comprehensive HubSpot API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.refresh_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize HubSpot service with database pool"""
        try:
            from db_oauth_hubspot import get_user_hubspot_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_hubspot_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens["refresh_token"]
                self._initialized = True
                logger.info(f"HubSpot service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No HubSpot tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize HubSpot service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("HubSpot service not initialized. Call initialize() first.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def _make_request(self, method: str, endpoint: str, 
                           data: Dict[str, Any] = None, 
                           params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated API request with error handling"""
        try:
            url = f"{HUBSPOT_API_BASE}{endpoint}"
            
            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=self._get_headers(), params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=self._get_headers(), json=data, params=params)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=self._get_headers(), json=data, params=params)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=self._get_headers(), params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code == 401:
                    # Token expired, try to refresh
                    await self._refresh_token()
                    # Retry request with new token
                    return await self._make_request(method, endpoint, data, params)
                elif response.status_code >= 400:
                    error_data = response.text
                    logger.error(f"HubSpot API error {response.status_code}: {error_data}")
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}",
                        "details": error_data
                    }
                
                response.raise_for_status()
                return {
                    "success": True,
                    "data": response.json() if response.content else {}
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HubSpot API HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP error {e.response.status_code}",
                "details": e.response.text
            }
        except Exception as e:
            logger.error(f"HubSpot API request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _refresh_token(self):
        """Refresh access token"""
        try:
            refresh_url = "https://api.hubapi.com/oauth/v1/token"
            
            data = {
                "grant_type": "refresh_token",
                "client_id": os.getenv("HUBSPOT_CLIENT_ID"),
                "client_secret": os.getenv("HUBSPOT_CLIENT_SECRET"),
                "refresh_token": self.refresh_token
            }
            
            async with httpx.AsyncClient() as client:
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
                
        except Exception as e:
            logger.error(f"Failed to refresh HubSpot token: {e}")
            raise
    
    # Contacts Management
    async def get_contacts(self, limit: int = 100, after: str = None, 
                          properties: List[str] = None) -> Dict[str, Any]:
        """Get HubSpot contacts"""
        try:
            await self._ensure_initialized()
            
            # Default properties to fetch
            if not properties:
                properties = ["firstname", "lastname", "email", "phone", "company", "jobtitle", 
                            "website", "lifecyclestage", "createdate", "lastmodifieddate"]
            
            params = {
                "limit": limit,
                "properties": properties
            }
            
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", "/crm/v3/objects/contacts", params=params)
            
            if result["success"]:
                contacts = []
                for contact in result["data"].get("results", []):
                    contacts.append({
                        "id": contact.get("id"),
                        "properties": contact.get("properties", {}),
                        "createdAt": contact.get("createdAt"),
                        "updatedAt": contact.get("updatedAt"),
                        "archived": contact.get("archived", False),
                        "firstName": contact.get("properties", {}).get("firstname", ""),
                        "lastName": contact.get("properties", {}).get("lastname", ""),
                        "email": contact.get("properties", {}).get("email", ""),
                        "phone": contact.get("properties", {}).get("phone", ""),
                        "company": contact.get("properties", {}).get("company", ""),
                        "jobTitle": contact.get("properties", {}).get("jobtitle", ""),
                        "website": contact.get("properties", {}).get("website", ""),
                        "lifecycleStage": contact.get("properties", {}).get("lifecyclestage", ""),
                        "fullName": self._get_full_name(contact.get("properties", {})),
                        "hasEmail": bool(contact.get("properties", {}).get("email")),
                        "hasPhone": bool(contact.get("properties", {}).get("phone")),
                        "isCustomer": contact.get("properties", {}).get("lifecyclestage") == "customer"
                    })
                
                # Cache contacts
                await self.cache_contacts(contacts)
                
                return {
                    "success": True,
                    "data": contacts,
                    "total": len(contacts),
                    "paging": result["data"].get("paging", {})
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot contacts: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_contact(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            contact_data = {
                "properties": properties
            }
            
            result = await self._make_request("POST", "/crm/v3/objects/contacts", data=contact_data)
            
            if result["success"]:
                contact = result["data"]
                
                # Log activity
                await self.log_activity("create_contact", {
                    "contact_id": contact.get("id"),
                    "email": properties.get("email"),
                    "properties": properties
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": contact.get("id"),
                        "properties": contact.get("properties", {}),
                        "createdAt": contact.get("createdAt"),
                        "updatedAt": contact.get("updatedAt")
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            contact_data = {
                "properties": properties
            }
            
            result = await self._make_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", 
                                           data=contact_data)
            
            if result["success"]:
                contact = result["data"]
                
                # Log activity
                await self.log_activity("update_contact", {
                    "contact_id": contact_id,
                    "properties": properties
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": contact.get("id"),
                        "properties": contact.get("properties", {}),
                        "updatedAt": contact.get("updatedAt")
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to update HubSpot contact: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            result = await self._make_request("DELETE", f"/crm/v3/objects/contacts/{contact_id}")
            
            if result["success"]:
                # Log activity
                await self.log_activity("delete_contact", {
                    "contact_id": contact_id
                })
                
                return {
                    "success": True,
                    "message": "Contact deleted successfully"
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to delete HubSpot contact: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Companies Management
    async def get_companies(self, limit: int = 100, after: str = None, 
                          properties: List[str] = None) -> Dict[str, Any]:
        """Get HubSpot companies"""
        try:
            await self._ensure_initialized()
            
            # Default properties to fetch
            if not properties:
                properties = ["name", "domain", "industry", "description", "size", "revenue",
                            "phone", "website", "city", "state", "country", "createdate", 
                            "lastmodifieddate"]
            
            params = {
                "limit": limit,
                "properties": properties
            }
            
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", "/crm/v3/objects/companies", params=params)
            
            if result["success"]:
                companies = []
                for company in result["data"].get("results", []):
                    companies.append({
                        "id": company.get("id"),
                        "properties": company.get("properties", {}),
                        "createdAt": company.get("createdAt"),
                        "updatedAt": company.get("updatedAt"),
                        "archived": company.get("archived", False),
                        "name": company.get("properties", {}).get("name", ""),
                        "domain": company.get("properties", {}).get("domain", ""),
                        "industry": company.get("properties", {}).get("industry", ""),
                        "description": company.get("properties", {}).get("description", ""),
                        "size": company.get("properties", {}).get("size", ""),
                        "revenue": company.get("properties", {}).get("revenue", ""),
                        "phone": company.get("properties", {}).get("phone", ""),
                        "website": company.get("properties", {}).get("website", ""),
                        "city": company.get("properties", {}).get("city", ""),
                        "state": company.get("properties", {}).get("state", ""),
                        "country": company.get("properties", {}).get("country", ""),
                        "hasWebsite": bool(company.get("properties", {}).get("website")),
                        "hasPhone": bool(company.get("properties", {}).get("phone")),
                        "employeeCount": self._parse_employee_count(company.get("properties", {}).get("size", ""))
                    })
                
                # Cache companies
                await self.cache_companies(companies)
                
                return {
                    "success": True,
                    "data": companies,
                    "total": len(companies),
                    "paging": result["data"].get("paging", {})
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot companies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_company(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot company"""
        try:
            await self._ensure_initialized()
            
            company_data = {
                "properties": properties
            }
            
            result = await self._make_request("POST", "/crm/v3/objects/companies", data=company_data)
            
            if result["success"]:
                company = result["data"]
                
                # Log activity
                await self.log_activity("create_company", {
                    "company_id": company.get("id"),
                    "name": properties.get("name"),
                    "domain": properties.get("domain"),
                    "properties": properties
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": company.get("id"),
                        "properties": company.get("properties", {}),
                        "createdAt": company.get("createdAt"),
                        "updatedAt": company.get("updatedAt")
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to create HubSpot company: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Deals Management
    async def get_deals(self, limit: int = 100, after: str = None, 
                       properties: List[str] = None) -> Dict[str, Any]:
        """Get HubSpot deals"""
        try:
            await self._ensure_initialized()
            
            # Default properties to fetch
            if not properties:
                properties = ["dealname", "pipeline", "dealstage", "amount", "closedate",
                            "createdate", "lastmodifieddate", "hs_forecast_amount", 
                            "probability", "dealtype"]
            
            params = {
                "limit": limit,
                "properties": properties
            }
            
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", "/crm/v3/objects/deals", params=params)
            
            if result["success"]:
                deals = []
                for deal in result["data"].get("results", []):
                    deals.append({
                        "id": deal.get("id"),
                        "properties": deal.get("properties", {}),
                        "createdAt": deal.get("createdAt"),
                        "updatedAt": deal.get("updatedAt"),
                        "archived": deal.get("archived", False),
                        "dealName": deal.get("properties", {}).get("dealname", ""),
                        "pipeline": deal.get("properties", {}).get("pipeline", ""),
                        "dealStage": deal.get("properties", {}).get("dealstage", ""),
                        "amount": self._parse_amount(deal.get("properties", {}).get("amount", "0")),
                        "forecastAmount": self._parse_amount(deal.get("properties", {}).get("hs_forecast_amount", "0")),
                        "probability": self._parse_probability(deal.get("properties", {}).get("probability", "0")),
                        "dealType": deal.get("properties", {}).get("dealtype", ""),
                        "closeDate": deal.get("properties", {}).get("closedate", ""),
                        "isClosed": bool(deal.get("properties", {}).get("closedate")),
                        "isWon": self._is_deal_won(deal.get("properties", {}).get("dealstage", "")),
                        "hasAmount": bool(deal.get("properties", {}).get("amount", "0") != "0")
                    })
                
                # Cache deals
                await self.cache_deals(deals)
                
                return {
                    "success": True,
                    "data": deals,
                    "total": len(deals),
                    "paging": result["data"].get("paging", {})
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot deals: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_deal(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot deal"""
        try:
            await self._ensure_initialized()
            
            deal_data = {
                "properties": properties
            }
            
            result = await self._make_request("POST", "/crm/v3/objects/deals", data=deal_data)
            
            if result["success"]:
                deal = result["data"]
                
                # Log activity
                await self.log_activity("create_deal", {
                    "deal_id": deal.get("id"),
                    "deal_name": properties.get("dealname"),
                    "amount": properties.get("amount"),
                    "properties": properties
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": deal.get("id"),
                        "properties": deal.get("properties", {}),
                        "createdAt": deal.get("createdAt"),
                        "updatedAt": deal.get("updatedAt")
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to create HubSpot deal: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Tickets Management
    async def get_tickets(self, limit: int = 100, after: str = None, 
                         properties: List[str] = None) -> Dict[str, Any]:
        """Get HubSpot tickets"""
        try:
            await self._ensure_initialized()
            
            # Default properties to fetch
            if not properties:
                properties = ["subject", "content", "hs_pipeline", "hs_pipeline_stage",
                            "hs_ticket_category", "hs_ticket_priority", "createdate", 
                            "lastmodifieddate", "closed_date"]
            
            params = {
                "limit": limit,
                "properties": properties
            }
            
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", "/crm/v3/objects/tickets", params=params)
            
            if result["success"]:
                tickets = []
                for ticket in result["data"].get("results", []):
                    tickets.append({
                        "id": ticket.get("id"),
                        "properties": ticket.get("properties", {}),
                        "createdAt": ticket.get("createdAt"),
                        "updatedAt": ticket.get("updatedAt"),
                        "archived": ticket.get("archived", False),
                        "subject": ticket.get("properties", {}).get("subject", ""),
                        "content": ticket.get("properties", {}).get("content", ""),
                        "pipeline": ticket.get("properties", {}).get("hs_pipeline", ""),
                        "pipelineStage": ticket.get("properties", {}).get("hs_pipeline_stage", ""),
                        "category": ticket.get("properties", {}).get("hs_ticket_category", ""),
                        "priority": ticket.get("properties", {}).get("hs_ticket_priority", ""),
                        "closedDate": ticket.get("properties", {}).get("closed_date", ""),
                        "isClosed": bool(ticket.get("properties", {}).get("closed_date")),
                        "priorityLevel": self._get_priority_level(ticket.get("properties", {}).get("hs_ticket_priority", ""))
                    })
                
                # Cache tickets
                await self.cache_tickets(tickets)
                
                return {
                    "success": True,
                    "data": tickets,
                    "total": len(tickets),
                    "paging": result["data"].get("paging", {})
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot tickets: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Pipelines Management
    async def get_pipelines(self, object_type: str = "deals") -> Dict[str, Any]:
        """Get HubSpot pipelines"""
        try:
            await self._ensure_initialized()
            
            result = await self._make_request("GET", f"/crm/v3/pipelines/{object_type}")
            
            if result["success"]:
                pipelines = []
                for pipeline in result["data"].get("results", []):
                    stages = []
                    for stage in pipeline.get("stages", []):
                        stages.append({
                            "id": stage.get("id"),
                            "label": stage.get("label"),
                            "displayOrder": stage.get("displayOrder", 0),
                            "metadata": stage.get("metadata", {}),
                            "isWon": stage.get("metadata", {}).get("isWon", False),
                            "isLost": stage.get("metadata", {}).get("isLost", False)
                        })
                    
                    pipelines.append({
                        "id": pipeline.get("id"),
                        "label": pipeline.get("label"),
                        "displayOrder": pipeline.get("displayOrder", 0),
                        "objectType": object_type,
                        "stages": stages,
                        "active": pipeline.get("active", True),
                        "stageCount": len(stages),
                        "wonStages": len([s for s in stages if s.get("isWon", False)]),
                        "lostStages": len([s for s in stages if s.get("isLost", False)])
                    })
                
                return {
                    "success": True,
                    "data": pipelines,
                    "total": len(pipelines)
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot pipelines: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Search and Analytics
    async def search_objects(self, object_type: str, query: str, 
                           limit: int = 50) -> Dict[str, Any]:
        """Search HubSpot objects"""
        try:
            await self._ensure_initialized()
            
            search_data = {
                "filters": [
                    {
                        "propertyName": "searchable_properties",
                        "operator": "CONTAINS_TOKEN",
                        "value": query
                    }
                ],
                "limit": limit
            }
            
            result = await self._make_request("POST", f"/crm/v3/objects/{object_type}/search", 
                                           data=search_data)
            
            if result["success"]:
                objects = result["data"].get("results", [])
                
                # Log search activity
                await self.log_activity("search_objects", {
                    "object_type": object_type,
                    "query": query,
                    "results_count": len(objects)
                })
                
                return {
                    "success": True,
                    "data": objects,
                    "total": len(objects)
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to search HubSpot objects: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_engagement_stats(self, start_date: str = None, 
                                end_date: str = None) -> Dict[str, Any]:
        """Get engagement statistics"""
        try:
            await self._ensure_initialized()
            
            # Get basic stats
            contacts_result = await self.get_contacts(limit=1)
            companies_result = await self.get_companies(limit=1)
            deals_result = await self.get_deals(limit=1)
            tickets_result = await self.get_tickets(limit=1)
            
            # Calculate stats
            total_contacts = contacts_result.get("success", False) and len(contacts_result.get("data", [])) > 0
            total_companies = companies_result.get("success", False) and len(companies_result.get("data", [])) > 0
            total_deals = deals_result.get("success", False) and len(deals_result.get("data", [])) > 0
            total_tickets = tickets_result.get("success", False) and len(tickets_result.get("data", [])) > 0
            
            # Get more detailed data for actual counts
            if total_contacts:
                contacts_full = await self.get_contacts(limit=100)
                total_contacts = len(contacts_full.get("data", []))
            
            if total_companies:
                companies_full = await self.get_companies(limit=100)
                total_companies = len(companies_full.get("data", []))
            
            if total_deals:
                deals_full = await self.get_deals(limit=100)
                total_deals = len(deals_full.get("data", []))
                # Calculate deal value
                total_deal_value = sum(deal.get("amount", 0) for deal in deals_full.get("data", []))
                won_deals = len([d for d in deals_full.get("data", []) if d.get("isWon", False)])
            
            if total_tickets:
                tickets_full = await self.get_tickets(limit=100)
                total_tickets = len(tickets_full.get("data", []))
                open_tickets = len([t for t in tickets_full.get("data", []) if not t.get("isClosed", False)])
            
            return {
                "success": True,
                "data": {
                    "contacts": {
                        "total": total_contacts,
                        "customers": 0  # Would need additional calculation
                    },
                    "companies": {
                        "total": total_companies,
                        "industries": set()  # Would need additional calculation
                    },
                    "deals": {
                        "total": total_deals,
                        "won": total_deals > 0 and won_deals or 0,
                        "totalValue": total_deal_value if total_deals > 0 else 0
                    },
                    "tickets": {
                        "total": total_tickets,
                        "open": total_tickets > 0 and open_tickets or 0,
                        "closed": total_tickets > 0 and (total_tickets - open_tickets) or 0
                    },
                    "dateRange": {
                        "startDate": start_date,
                        "endDate": end_date
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot engagement stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Helper methods
    def _get_full_name(self, properties: Dict[str, Any]) -> str:
        """Get full name from properties"""
        first = properties.get("firstname", "")
        last = properties.get("lastname", "")
        return f"{first} {last}".strip()
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        try:
            return float(amount_str.replace("$", "").replace(",", "").strip() or "0")
        except:
            return 0.0
    
    def _parse_probability(self, probability_str: str) -> float:
        """Parse probability string to float"""
        try:
            return float(probability_str.replace("%", "").strip() or "0") / 100
        except:
            return 0.0
    
    def _parse_employee_count(self, size_str: str) -> int:
        """Parse employee count string to int"""
        try:
            if not size_str:
                return 0
            # Extract numeric value from strings like "51-200", "501-1000"
            import re
            numbers = re.findall(r'\d+', size_str)
            if numbers:
                return max(int(n) for n in numbers)
            return 0
        except:
            return 0
    
    def _is_deal_won(self, deal_stage: str) -> bool:
        """Check if deal is won"""
        # Common won stage patterns
        won_patterns = ["closed won", "won", "closed", "signed", "contract"]
        return any(pattern in deal_stage.lower() for pattern in won_patterns)
    
    def _get_priority_level(self, priority_str: str) -> int:
        """Get priority level from priority string"""
        priority_map = {
            "high": 3,
            "medium": 2,
            "low": 1,
            "urgent": 4
        }
        return priority_map.get(priority_str.lower(), 2)
    
    # Caching methods
    async def cache_contacts(self, contacts: List[Dict[str, Any]]) -> bool:
        """Cache HubSpot contact data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hubspot_contacts_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        contact_id VARCHAR(255) NOT NULL,
                        contact_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, contact_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_user_id ON hubspot_contacts_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_contact_id ON hubspot_contacts_cache(contact_id);
                """)
                
                # Update cache
                for contact in contacts:
                    await conn.execute("""
                        INSERT INTO hubspot_contacts_cache 
                        (user_id, contact_id, contact_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, contact_id)
                        DO UPDATE SET 
                            contact_data = EXCLUDED.contact_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, contact["id"], json.dumps(contact))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache HubSpot contacts: {e}")
            return False
    
    async def cache_companies(self, companies: List[Dict[str, Any]]) -> bool:
        """Cache HubSpot company data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hubspot_companies_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        company_id VARCHAR(255) NOT NULL,
                        company_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, company_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_hubspot_companies_user_id ON hubspot_companies_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_hubspot_companies_company_id ON hubspot_companies_cache(company_id);
                """)
                
                # Update cache
                for company in companies:
                    await conn.execute("""
                        INSERT INTO hubspot_companies_cache 
                        (user_id, company_id, company_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, company_id)
                        DO UPDATE SET 
                            company_data = EXCLUDED.company_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, company["id"], json.dumps(company))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache HubSpot companies: {e}")
            return False
    
    async def cache_deals(self, deals: List[Dict[str, Any]]) -> bool:
        """Cache HubSpot deal data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hubspot_deals_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        deal_id VARCHAR(255) NOT NULL,
                        deal_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, deal_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_hubspot_deals_user_id ON hubspot_deals_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_hubspot_deals_deal_id ON hubspot_deals_cache(deal_id);
                """)
                
                # Update cache
                for deal in deals:
                    await conn.execute("""
                        INSERT INTO hubspot_deals_cache 
                        (user_id, deal_id, deal_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, deal_id)
                        DO UPDATE SET 
                            deal_data = EXCLUDED.deal_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, deal["id"], json.dumps(deal))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache HubSpot deals: {e}")
            return False
    
    async def cache_tickets(self, tickets: List[Dict[str, Any]]) -> bool:
        """Cache HubSpot ticket data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hubspot_tickets_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        ticket_id VARCHAR(255) NOT NULL,
                        ticket_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, ticket_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_user_id ON hubspot_tickets_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_ticket_id ON hubspot_tickets_cache(ticket_id);
                """)
                
                # Update cache
                for ticket in tickets:
                    await conn.execute("""
                        INSERT INTO hubspot_tickets_cache 
                        (user_id, ticket_id, ticket_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, ticket_id)
                        DO UPDATE SET 
                            ticket_data = EXCLUDED.ticket_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, ticket["id"], json.dumps(ticket))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache HubSpot tickets: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log HubSpot activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hubspot_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_hubspot_activity_user_id ON hubspot_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_hubspot_activity_action ON hubspot_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO hubspot_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log HubSpot activity: {e}")
            return False