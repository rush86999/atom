"""
ATOM HubSpot Integration Service
Comprehensive HubSpot API integration for marketing automation and lead generation
Following ATOM integration patterns and conventions
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
import aiohttp
import logging
from loguru import logger

@dataclass
class HubSpotConfig:
    """HubSpot configuration class"""
    access_token: str
    api_base_url: str = "https://api.hubapi.com"
    private_app_token: Optional[str] = None
    environment: str = "production"
    
    def __post_init__(self):
        if self.environment == "sandbox":
            self.api_base_url = "https://api.hubspotqa.com"

class HubSpotService:
    """Enhanced HubSpot service class for API interactions"""
    
    def __init__(self, config: Optional[HubSpotConfig] = None):
        self.config = config or self._get_config_from_env()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.max_retries = 3
        self.rate_limit_delay = 0.1  # 100ms between requests
        
    def _get_config_from_env(self) -> HubSpotConfig:
        """Load configuration from environment variables"""
        return HubSpotConfig(
            access_token=os.getenv("HUBSPOT_ACCESS_TOKEN", ""),
            private_app_token=os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"),
            environment=os.getenv("HUBSPOT_ENVIRONMENT", "production")
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self.session or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            if self.config.private_app_token:
                headers["Authorization"] = f"Bearer {self.config.private_app_token}"
                
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout
            )
        return self.session
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None,
        use_pagination: bool = False
    ) -> Dict[str, Any]:
        """Make authenticated request to HubSpot API with retry logic and rate limiting"""
        session = await self._get_session()
        url = f"{self.config.api_base_url}{endpoint}"
        
        all_results = []
        has_more = True
        offset = 0
        limit = params.get('limit', 100) if params else 100
        
        while has_more and (use_pagination or len(all_results) == 0):
            # Apply rate limiting
            if len(all_results) > 0:
                await asyncio.sleep(self.rate_limit_delay)
            
            # Add pagination parameters
            paginated_params = params.copy() if params else {}
            if use_pagination:
                paginated_params.update({
                    'limit': limit,
                    'after': offset if offset > 0 else None
                })
            
            for attempt in range(self.max_retries):
                try:
                    async with session.request(
                        method=method,
                        url=url,
                        json=data,
                        params=paginated_params,
                        headers=session.headers
                    ) as response:
                        if response.status == 401:
                            raise Exception("Invalid or expired access token")
                        elif response.status == 429:
                            retry_after = int(response.headers.get('X-Retry-After', 5))
                            await asyncio.sleep(retry_after)
                            continue
                        elif response.status >= 400:
                            error_text = await response.text()
                            raise Exception(f"HubSpot API error: {response.status} - {error_text}")
                        
                        if response.status == 204:  # No Content
                            return {"success": True}
                        
                        result = await response.json()
                        
                        # Handle HubSpot API response structure
                        if 'status' in result and result['status'] == 'error':
                            raise Exception(f"HubSpot API error: {result}")
                        
                        # Handle pagination
                        if use_pagination and 'paging' in result:
                            paging = result.get('paging', {})
                            if 'next' in paging:
                                offset = paging['next'].get('after', 0)
                                all_results.extend(result.get('results', []))
                                continue
                            else:
                                all_results.extend(result.get('results', []))
                                has_more = False
                        else:
                            return result
                            
                except aiohttp.ClientError as e:
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Request failed after {self.max_retries} attempts: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
        
        if use_pagination:
            return {
                "results": all_results,
                "total": len(all_results)
            }
        
        raise Exception("Request failed after all retries")

# Contact management
    async def get_contacts(
        self, 
        limit: int = 30,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company: Optional[str] = None,
        created_after: Optional[date] = None,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get list of contacts with optional filtering"""
        params = {
            "limit": limit
        }
        
        # Build search filters
        filter_groups = []
        if email:
            filter_groups.append({
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            })
        if first_name:
            filter_groups.append({
                "filters": [{
                    "propertyName": "firstname",
                    "operator": "CONTAINS_TOKEN",
                    "value": first_name
                }]
            })
        if last_name:
            filter_groups.append({
                "filters": [{
                    "propertyName": "lastname",
                    "operator": "CONTAINS_TOKEN",
                    "value": last_name
                }]
            })
        if company:
            filter_groups.append({
                "filters": [{
                    "propertyName": "company",
                    "operator": "CONTAINS_TOKEN",
                    "value": company
                }]
            })
        if created_after:
            filter_groups.append({
                "filters": [{
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": int(created_after.timestamp() * 1000)
                }]
            })
        
        if filter_groups:
            params["filterGroups"] = json.dumps(filter_groups)
        
        # Set properties to return
        if properties:
            params["properties"] = properties
        else:
            # Default properties to return
            params["properties"] = [
                "email", "firstname", "lastname", "phone", "company",
                "lifecyclestage", "leadstatus", "hs_lead_status", "createdate", "lastmodifieddate"
            ]
        
        return await self._make_request("POST", "/crm/v3/objects/contacts/search", params=params, use_pagination=True)
    
    async def get_contact(self, contact_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get specific contact by ID"""
        params = {}
        if properties:
            params["properties"] = properties
        else:
            params["properties"] = [
                "email", "firstname", "lastname", "phone", "company",
                "lifecyclestage", "leadstatus", "hs_lead_status", "createdate", "lastmodifieddate"
            ]
        
        return await self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)
    
    async def create_contact(
        self, 
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        lifecycle_stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new contact"""
        contact_data = {
            "properties": {
                "email": email
            }
        }
        
        if first_name:
            contact_data["properties"]["firstname"] = first_name
        if last_name:
            contact_data["properties"]["lastname"] = last_name
        if phone:
            contact_data["properties"]["phone"] = phone
        if company:
            contact_data["properties"]["company"] = company
        if lifecycle_stage:
            contact_data["properties"]["lifecyclestage"] = lifecycle_stage
        
        # Add custom properties
        if properties:
            contact_data["properties"].update(properties)
        
        return await self._make_request("POST", "/crm/v3/objects/contacts", data=contact_data)
    
    async def update_contact(
        self, 
        contact_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        lifecycle_stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update existing contact"""
        contact_data = {
            "properties": {}
        }
        
        if email:
            contact_data["properties"]["email"] = email
        if first_name:
            contact_data["properties"]["firstname"] = first_name
        if last_name:
            contact_data["properties"]["lastname"] = last_name
        if phone:
            contact_data["properties"]["phone"] = phone
        if company:
            contact_data["properties"]["company"] = company
        if lifecycle_stage:
            contact_data["properties"]["lifecyclestage"] = lifecycle_stage
        
        # Add custom properties
        if properties:
            contact_data["properties"].update(properties)
        
        return await self._make_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", data=contact_data)
    
    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete contact"""
        return await self._make_request("DELETE", f"/crm/v3/objects/contacts/{contact_id}")

# Company management
    async def get_companies(
        self, 
        limit: int = 30,
        domain: Optional[str] = None,
        name: Optional[str] = None,
        industry: Optional[str] = None,
        state: Optional[str] = None,
        created_after: Optional[date] = None,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get list of companies with optional filtering"""
        params = {
            "limit": limit
        }
        
        # Build search filters
        filter_groups = []
        if domain:
            filter_groups.append({
                "filters": [{
                    "propertyName": "domain",
                    "operator": "EQ",
                    "value": domain
                }]
            })
        if name:
            filter_groups.append({
                "filters": [{
                    "propertyName": "name",
                    "operator": "CONTAINS_TOKEN",
                    "value": name
                }]
            })
        if industry:
            filter_groups.append({
                "filters": [{
                    "propertyName": "industry",
                    "operator": "EQ",
                    "value": industry
                }]
            })
        if state:
            filter_groups.append({
                "filters": [{
                    "propertyName": "state",
                    "operator": "EQ",
                    "value": state
                }]
            })
        if created_after:
            filter_groups.append({
                "filters": [{
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": int(created_after.timestamp() * 1000)
                }]
            })
        
        if filter_groups:
            params["filterGroups"] = json.dumps(filter_groups)
        
        # Set properties to return
        if properties:
            params["properties"] = properties
        else:
            # Default properties to return
            params["properties"] = [
                "domain", "name", "description", "industry", "state", "country",
                "phone", "website", "employee_count", "annualrevenue", "createdate", "lastmodifieddate"
            ]
        
        return await self._make_request("POST", "/crm/v3/objects/companies/search", params=params, use_pagination=True)
    
    async def get_company(self, company_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get specific company by ID"""
        params = {}
        if properties:
            params["properties"] = properties
        else:
            params["properties"] = [
                "domain", "name", "description", "industry", "state", "country",
                "phone", "website", "employee_count", "annualrevenue", "createdate", "lastmodifieddate"
            ]
        
        return await self._make_request("GET", f"/crm/v3/objects/companies/{company_id}", params=params)
    
    async def create_company(
        self, 
        name: str,
        domain: Optional[str] = None,
        description: Optional[str] = None,
        industry: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        employee_count: Optional[int] = None,
        annual_revenue: Optional[float] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new company"""
        company_data = {
            "properties": {
                "name": name
            }
        }
        
        if domain:
            company_data["properties"]["domain"] = domain
        if description:
            company_data["properties"]["description"] = description
        if industry:
            company_data["properties"]["industry"] = industry
        if state:
            company_data["properties"]["state"] = state
        if country:
            company_data["properties"]["country"] = country
        if phone:
            company_data["properties"]["phone"] = phone
        if website:
            company_data["properties"]["website"] = website
        if employee_count:
            company_data["properties"]["employee_count"] = str(employee_count)
        if annual_revenue:
            company_data["properties"]["annualrevenue"] = str(annual_revenue)
        
        # Add custom properties
        if properties:
            company_data["properties"].update(properties)
        
        return await self._make_request("POST", "/crm/v3/objects/companies", data=company_data)
    
    async def update_company(
        self, 
        company_id: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        description: Optional[str] = None,
        industry: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        employee_count: Optional[int] = None,
        annual_revenue: Optional[float] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update existing company"""
        company_data = {
            "properties": {}
        }
        
        if name:
            company_data["properties"]["name"] = name
        if domain:
            company_data["properties"]["domain"] = domain
        if description:
            company_data["properties"]["description"] = description
        if industry:
            company_data["properties"]["industry"] = industry
        if state:
            company_data["properties"]["state"] = state
        if country:
            company_data["properties"]["country"] = country
        if phone:
            company_data["properties"]["phone"] = phone
        if website:
            company_data["properties"]["website"] = website
        if employee_count:
            company_data["properties"]["employee_count"] = str(employee_count)
        if annual_revenue:
            company_data["properties"]["annualrevenue"] = str(annual_revenue)
        
        # Add custom properties
        if properties:
            company_data["properties"].update(properties)
        
        return await self._make_request("PATCH", f"/crm/v3/objects/companies/{company_id}", data=company_data)
    
    async def delete_company(self, company_id: str) -> Dict[str, Any]:
        """Delete company"""
        return await self._make_request("DELETE", f"/crm/v3/objects/companies/{company_id}")

# Deal/Pipeline management
    async def get_deals(
        self, 
        limit: int = 30,
        deal_name: Optional[str] = None,
        deal_stage: Optional[str] = None,
        amount: Optional[float] = None,
        closed_won: Optional[bool] = None,
        created_after: Optional[date] = None,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get list of deals with optional filtering"""
        params = {
            "limit": limit
        }
        
        # Build search filters
        filter_groups = []
        if deal_name:
            filter_groups.append({
                "filters": [{
                    "propertyName": "dealname",
                    "operator": "CONTAINS_TOKEN",
                    "value": deal_name
                }]
            })
        if deal_stage:
            filter_groups.append({
                "filters": [{
                    "propertyName": "dealstage",
                    "operator": "EQ",
                    "value": deal_stage
                }]
            })
        if amount is not None:
            filter_groups.append({
                "filters": [{
                    "propertyName": "amount",
                    "operator": "GTE",
                    "value": amount
                }]
            })
        if closed_won is not None:
            filter_groups.append({
                "filters": [{
                    "propertyName": "closedate",
                    "operator": "HAS_PROPERTY" if closed_won else "NOT_HAS_PROPERTY"
                }]
            })
        if created_after:
            filter_groups.append({
                "filters": [{
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": int(created_after.timestamp() * 1000)
                }]
            })
        
        if filter_groups:
            params["filterGroups"] = json.dumps(filter_groups)
        
        # Set properties to return
        if properties:
            params["properties"] = properties
        else:
            # Default properties to return
            params["properties"] = [
                "dealname", "dealstage", "pipeline", "amount", "closedate",
                "createdate", "lastmodifieddate", "hs_forecast_amount"
            ]
        
        return await self._make_request("POST", "/crm/v3/objects/deals/search", params=params, use_pagination=True)
    
    async def get_deal(self, deal_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get specific deal by ID"""
        params = {}
        if properties:
            params["properties"] = properties
        else:
            params["properties"] = [
                "dealname", "dealstage", "pipeline", "amount", "closedate",
                "createdate", "lastmodifieddate", "hs_forecast_amount"
            ]
        
        return await self._make_request("GET", f"/crm/v3/objects/deals/{deal_id}", params=params)
    
    async def create_deal(
        self, 
        deal_name: str,
        amount: Optional[float] = None,
        pipeline: Optional[str] = None,
        deal_stage: Optional[str] = None,
        close_date: Optional[date] = None,
        contact_id: Optional[str] = None,
        company_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new deal"""
        deal_data = {
            "properties": {
                "dealname": deal_name
            }
        }
        
        if amount:
            deal_data["properties"]["amount"] = str(amount)
        if pipeline:
            deal_data["properties"]["pipeline"] = pipeline
        if deal_stage:
            deal_data["properties"]["dealstage"] = deal_stage
        if close_date:
            deal_data["properties"]["closedate"] = int(close_date.timestamp() * 1000)
        
        # Add custom properties
        if properties:
            deal_data["properties"].update(properties)
        
        result = await self._make_request("POST", "/crm/v3/objects/deals", data=deal_data)
        
        # Associate with contact and company if provided
        if contact_id:
            await self._associate_deal_with_contact(result['id'], contact_id)
        if company_id:
            await self._associate_deal_with_company(result['id'], company_id)
        
        return result
    
    async def update_deal(
        self, 
        deal_id: str,
        deal_name: Optional[str] = None,
        amount: Optional[float] = None,
        pipeline: Optional[str] = None,
        deal_stage: Optional[str] = None,
        close_date: Optional[date] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update existing deal"""
        deal_data = {
            "properties": {}
        }
        
        if deal_name:
            deal_data["properties"]["dealname"] = deal_name
        if amount:
            deal_data["properties"]["amount"] = str(amount)
        if pipeline:
            deal_data["properties"]["pipeline"] = pipeline
        if deal_stage:
            deal_data["properties"]["dealstage"] = deal_stage
        if close_date:
            deal_data["properties"]["closedate"] = int(close_date.timestamp() * 1000)
        
        # Add custom properties
        if properties:
            deal_data["properties"].update(properties)
        
        return await self._make_request("PATCH", f"/crm/v3/objects/deals/{deal_id}", data=deal_data)
    
    async def delete_deal(self, deal_id: str) -> Dict[str, Any]:
        """Delete deal"""
        return await self._make_request("DELETE", f"/crm/v3/objects/deals/{deal_id}")
    
    async def _associate_deal_with_contact(self, deal_id: str, contact_id: str) -> Dict[str, Any]:
        """Associate deal with contact"""
        association_data = {
            "inputs": [{
                "from": {
                    "id": contact_id
                },
                "to": {
                    "id": deal_id
                },
                "type": "deal_to_contact"
            }]
        }
        return await self._make_request("POST", "/crm/v3/associations/deal/contact", data=association_data)
    
    async def _associate_deal_with_company(self, deal_id: str, company_id: str) -> Dict[str, Any]:
        """Associate deal with company"""
        association_data = {
            "inputs": [{
                "from": {
                    "id": company_id
                },
                "to": {
                    "id": deal_id
                },
                "type": "company_to_deal"
            }]
        }
        return await self._make_request("POST", "/crm/v3/associations/company/deal", data=association_data)

# Marketing campaigns
    async def get_campaigns(
        self, 
        limit: int = 30,
        campaign_name: Optional[str] = None,
        status: Optional[str] = None,
        created_after: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get list of marketing campaigns"""
        params = {
            "limit": limit
        }
        
        # Build search filters
        filter_groups = []
        if campaign_name:
            filter_groups.append({
                "filters": [{
                    "propertyName": "name",
                    "operator": "CONTAINS_TOKEN",
                    "value": campaign_name
                }]
            })
        if status:
            filter_groups.append({
                "filters": [{
                    "propertyName": "status",
                    "operator": "EQ",
                    "value": status
                }]
            })
        if created_after:
            filter_groups.append({
                "filters": [{
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": int(created_after.timestamp() * 1000)
                }]
            })
        
        if filter_groups:
            params["filterGroups"] = json.dumps(filter_groups)
        
        return await self._make_request("POST", "/marketing/v3/campaigns/search", params=params, use_pagination=True)
    
    async def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Get specific campaign by ID"""
        return await self._make_request("GET", f"/marketing/v3/campaigns/{campaign_id}")
    
    async def create_campaign(
        self, 
        campaign_name: str,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = "DRAFT",
        campaign_type: Optional[str] = "EMAIL",
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new marketing campaign"""
        campaign_data = {
            "campaignName": campaign_name,
            "campaignType": campaign_type,
            "status": status
        }
        
        if subject:
            campaign_data["subject"] = subject
        if content:
            campaign_data["content"] = content
        
        # Add custom properties
        if properties:
            campaign_data.update(properties)
        
        return await self._make_request("POST", "/marketing/v3/campaigns", data=campaign_data)
    
    async def get_pipelines(self) -> Dict[str, Any]:
        """Get all sales pipelines"""
        return await self._make_request("GET", "/crm/v3/pipelines/deals")
    
    async def get_pipeline_stages(self, pipeline_id: str) -> Dict[str, Any]:
        """Get stages for a specific pipeline"""
        return await self._make_request("GET", f"/crm/v3/pipelines/deals/{pipeline_id}/stages")
    
    # Analytics and reporting
    async def get_deal_analytics(
        self, 
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get deal analytics and metrics"""
        params = {}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()
        if properties:
            params["properties"] = properties
        
        return await self._make_request("GET", "/crm/v3/objects/deals/analytics", params=params)
    
    async def get_contact_analytics(
        self, 
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get contact analytics and metrics"""
        params = {}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()
        if properties:
            params["properties"] = properties
        
        return await self._make_request("GET", "/crm/v3/objects/contacts/analytics", params=params)
    
    async def get_campaign_analytics(
        self, 
        campaign_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get campaign analytics and metrics"""
        params = {}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()
        
        return await self._make_request("GET", f"/marketing/v3/campaigns/{campaign_id}/analytics", params=params)
    
    # Lead nurturing
    async def get_lead_lists(self, limit: int = 30) -> Dict[str, Any]:
        """Get all lead lists"""
        params = {"limit": limit}
        return await self._make_request("GET", "/marketing/v3/lead-lists", params=params, use_pagination=True)
    
    async def create_lead_list(
        self, 
        list_name: str,
        description: Optional[str] = None,
        processing_type: str = "MANUAL"
    ) -> Dict[str, Any]:
        """Create a new lead list"""
        list_data = {
            "name": list_name,
            "processingType": processing_type
        }
        
        if description:
            list_data["description"] = description
        
        return await self._make_request("POST", "/marketing/v3/lead-lists", data=list_data)
    
    async def add_contacts_to_list(self, list_id: str, contact_ids: List[str]) -> Dict[str, Any]:
        """Add contacts to a lead list"""
        list_data = {
            "inputs": [
                {"id": contact_id} for contact_id in contact_ids
            ]
        }
        
        return await self._make_request("POST", f"/marketing/v3/lead-lists/{list_id}/memberships", data=list_data)
    
    async def remove_contacts_from_list(self, list_id: str, contact_ids: List[str]) -> Dict[str, Any]:
        """Remove contacts from a lead list"""
        list_data = {
            "inputs": [
                {"id": contact_id} for contact_id in contact_ids
            ]
        }
        
        return await self._make_request("DELETE", f"/marketing/v3/lead-lists/{list_id}/memberships", data=list_data)
    
    # Email marketing
    async def send_email_to_contacts(
        self, 
        template_id: str,
        contact_ids: List[str],
        send_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Send email to specific contacts"""
        email_data = {
            "templateId": template_id,
            "message": {
                "to": contact_ids
            }
        }
        
        if send_at:
            email_data["sendAt"] = int(send_at.timestamp() * 1000)
        
        return await self._make_request("POST", "/marketing/v3/transactional/single-email/send", data=email_data)
    
    async def get_email_templates(self, limit: int = 30) -> Dict[str, Any]:
        """Get all email templates"""
        params = {"limit": limit}
        return await self._make_request("GET", "/marketing/v3/marketing-emails/templates", params=params, use_pagination=True)
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Utility functions for response formatting
def format_hubspot_response(data: Any, service: str = "hubspot") -> Dict[str, Any]:
    """Format successful HubSpot response"""
    return {
        "ok": True,
        "data": data,
        "service": service,
        "timestamp": datetime.utcnow().isoformat()
    }

def format_hubspot_error_response(error_msg: str, service: str = "hubspot") -> Dict[str, Any]:
    """Format error response"""
    return {
        "ok": False,
        "error": {
            "code": "HUBSPOT_ERROR",
            "message": error_msg,
            "service": service
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# HubSpot service factory
def create_hubspot_service(config: Optional[HubSpotConfig] = None) -> HubSpotService:
    """Factory function to create HubSpot service instance"""
    return HubSpotService(config)