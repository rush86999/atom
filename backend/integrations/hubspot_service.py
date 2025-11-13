"""
HubSpot Service for ATOM Platform
Provides comprehensive HubSpot integration functionality
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import requests
from urllib.parse import urljoin, urlencode

logger = logging.getLogger(__name__)

class HubSpotService:
    """HubSpot API integration service"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('HUBSPOT_ACCESS_TOKEN')
        self.base_url = "https://api.hubapi.com"
        self.session = requests.Session()
        
        if self.access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-Platform/1.0'
            })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test HubSpot API connection"""
        try:
            response = self.session.get(f"{self.base_url}/crm/v3/objects/owners")
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "message": "HubSpot connection successful",
                    "authenticated": True,
                    "owners_found": len(data.get('results', []))
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"HubSpot connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_contacts(self, limit: int = 100, after: str = None,
                    properties: List[str] = None) -> Dict[str, Any]:
        """Get contacts from HubSpot"""
        try:
            params = {'limit': limit}
            if after:
                params['after'] = after
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'firstname,lastname,email,phone,company,jobtitle,createdate,hs_lead_status'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/contacts",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            return {"results": [], "paging": None}
    
    def get_contact(self, contact_id: str, properties: List[str] = None) -> Optional[Dict[str, Any]]:
        """Get specific contact"""
        try:
            params = {}
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'firstname,lastname,email,phone,company,jobtitle,createdate,hs_lead_status'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get contact {contact_id}: {e}")
            return None
    
    def create_contact(self, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new contact"""
        try:
            data = {"properties": properties}
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create contact: {e}")
            return None
    
    def update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a contact"""
        try:
            data = {"properties": properties}
            response = self.session.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update contact {contact_id}: {e}")
            return None
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact"""
        try:
            response = self.session.delete(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete contact {contact_id}: {e}")
            return False
    
    def get_companies(self, limit: int = 100, after: str = None,
                     properties: List[str] = None) -> Dict[str, Any]:
        """Get companies from HubSpot"""
        try:
            params = {'limit': limit}
            if after:
                params['after'] = after
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'name,domain,phone,address,city,state,country,industry,createdate'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/companies",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get companies: {e}")
            return {"results": [], "paging": None}
    
    def get_company(self, company_id: str, properties: List[str] = None) -> Optional[Dict[str, Any]]:
        """Get specific company"""
        try:
            params = {}
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'name,domain,phone,address,city,state,country,industry,createdate'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/companies/{company_id}",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get company {company_id}: {e}")
            return None
    
    def create_company(self, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new company"""
        try:
            data = {"properties": properties}
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/companies",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create company: {e}")
            return None
    
    def update_company(self, company_id: str, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a company"""
        try:
            data = {"properties": properties}
            response = self.session.patch(
                f"{self.base_url}/crm/v3/objects/companies/{company_id}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update company {company_id}: {e}")
            return None
    
    def get_deals(self, limit: int = 100, after: str = None,
                 properties: List[str] = None) -> Dict[str, Any]:
        """Get deals from HubSpot"""
        try:
            params = {'limit': limit}
            if after:
                params['after'] = after
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'dealname,amount,closedate,pipeline,dealstage,createdate,hs_predicted_amount'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/deals",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get deals: {e}")
            return {"results": [], "paging": None}
    
    def create_deal(self, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new deal"""
        try:
            data = {"properties": properties}
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/deals",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create deal: {e}")
            return None
    
    def update_deal(self, deal_id: str, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a deal"""
        try:
            data = {"properties": properties}
            response = self.session.patch(
                f"{self.base_url}/crm/v3/objects/deals/{deal_id}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update deal {deal_id}: {e}")
            return None
    
    def get_tickets(self, limit: int = 100, after: str = None,
                   properties: List[str] = None) -> Dict[str, Any]:
        """Get tickets from HubSpot"""
        try:
            params = {'limit': limit}
            if after:
                params['after'] = after
            if properties:
                params['properties'] = ','.join(properties)
            else:
                params['properties'] = 'subject,content,hs_pipeline,hs_pipeline_stage,createdate,hs_ticket_priority'
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/tickets",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return {"results": [], "paging": None}
    
    def create_ticket(self, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new ticket"""
        try:
            data = {"properties": properties}
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/tickets",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None
    
    def search_objects(self, object_type: str, query: str, limit: int = 50) -> Dict[str, Any]:
        """Search HubSpot objects"""
        try:
            data = {
                "query": query,
                "limit": limit,
                "types": [object_type]
            }
            
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/search",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to search {object_type}: {e}")
            return {"results": [], "total": 0}
    
    def associate_objects(self, object_type_from: str, object_id_from: str,
                        object_type_to: str, object_id_to: str,
                        association_type: str) -> bool:
        """Associate two objects"""
        try:
            association_url = f"{self.base_url}/crm/v3/associations/{object_type_from}/{object_id_from}/{object_type_to}/{object_id_to}"
            
            data = [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type}]
            
            response = self.session.put(association_url, json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to associate objects: {e}")
            return False
    
    def get_engagements(self, contact_id: str = None, company_id: str = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get engagements for a contact or company"""
        try:
            params = {'limit': limit}
            
            if contact_id:
                params['contactIds'] = contact_id
            if company_id:
                params['companyIds'] = company_id
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/engagements",
                params=params
            )
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            logger.error(f"Failed to get engagements: {e}")
            return []
    
    def create_note(self, properties: Dict[str, Any], object_type: str = None,
                   object_id: str = None) -> Optional[Dict[str, Any]]:
        """Create a note"""
        try:
            data = {"properties": properties}
            
            if object_type and object_id:
                data['associations'] = [
                    {
                        "to": {"id": object_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": object_type}]
                    }
                ]
            
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/notes",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create note: {e}")
            return None
    
    def create_task(self, properties: Dict[str, Any], object_type: str = None,
                  object_id: str = None) -> Optional[Dict[str, Any]]:
        """Create a task"""
        try:
            data = {"properties": properties}
            
            if object_type and object_id:
                data['associations'] = [
                    {
                        "to": {"id": object_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": object_type}]
                    }
                ]
            
            response = self.session.post(
                f"{self.base_url}/crm/v3/objects/tasks",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None
    
    def get_owners(self) -> List[Dict[str, Any]]:
        """Get HubSpot owners"""
        try:
            response = self.session.get(f"{self.base_url}/crm/v3/objects/owners")
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            logger.error(f"Failed to get owners: {e}")
            return []
    
    def get_pipelines(self, object_type: str = "deals") -> List[Dict[str, Any]]:
        """Get pipelines for an object type"""
        try:
            response = self.session.get(
                f"{self.base_url}/crm/v3/pipelines/{object_type}"
            )
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            logger.error(f"Failed to get pipelines for {object_type}: {e}")
            return []
    
    def get_pipeline_stages(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Get stages in a pipeline"""
        try:
            response = self.session.get(
                f"{self.base_url}/crm/v3/pipelines/{pipeline_id}/stages"
            )
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            logger.error(f"Failed to get pipeline stages: {e}")
            return []
    
    def get_contacts_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently created/updated contacts"""
        try:
            # Sort by createdate descending
            params = {
                'limit': limit,
                'properties': 'firstname,lastname,email,phone,company,jobtitle,createdate,hs_lead_status',
                'sort': '-createdate'
            }
            
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/contacts",
                params=params
            )
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            logger.error(f"Failed to get recent contacts: {e}")
            return []
    
    def get_deal_insights(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get insights for a specific deal"""
        try:
            response = self.session.get(
                f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
            )
            response.raise_for_status()
            
            deal_data = response.json()
            return {
                "deal": deal_data,
                "score": deal_data.get('properties', {}).get('hs_calculated_deal_probability'),
                "days_to_close": deal_data.get('properties', {}).get('hs_time_to_close'),
                "forecast_amount": deal_data.get('properties', {}).get('hs_forecast_amount')
            }
        except Exception as e:
            logger.error(f"Failed to get deal insights for {deal_id}: {e}")
            return None

# Singleton instance for global access
hubspot_service = HubSpotService()

def get_hubspot_service() -> HubSpotService:
    """Get HubSpot service instance"""
    return hubspot_service