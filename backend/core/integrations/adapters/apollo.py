"""
Apollo Integration Adapter

Provides a unified interface for Apollo.io services within the IntegrationFactory.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ApolloAdapter:
    """
    Adapter for Apollo.io API integration.
    """

    def __init__(self, db=None, workspace_id: str = None):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "apollo"
        self.base_url = "https://api.apollo.io/v1"
        
        # In a real scenario, we would fetch the API key from the database 
        # using workspace_id and service_name from UserConnection table.
        # For now, we'll assume it's provided or handled by the factory/caller context.
        self._api_key: Optional[str] = os.getenv("APOLLO_API_KEY")

    async def test_connection(self) -> bool:
        """Test the Apollo API connection"""
        if not self._api_key:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/auth/health",
                    params={"api_key": self._api_key}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Apollo connection test failed: {e}")
            return False

    async def get_data(self, data_type: str, query: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generic method to fetch data from Apollo.
        
        Supported data_types:
        - people: Search for people
        - search: Search for people (alias)
        - enrichment: Enrich a person by email
        """
        if not self._api_key:
            raise ValueError("Apollo API key not configured")

        async with httpx.AsyncClient() as client:
            if data_type in ["people", "search"]:
                # Search people
                search_query = query or kwargs.get("q_description", "")
                response = await client.post(
                    f"{self.base_url}/mixed_people/search",
                    params={"api_key": self._api_key},
                    json={"q_description": search_query}
                )
                response.raise_for_status()
                result = response.json()
                return {"ok": True, "data": result.get("people", [])}
            
            elif data_type == "enrichment":
                # Enrich person
                email = query or kwargs.get("email")
                if not email:
                    raise ValueError("Email is required for enrichment")
                
                response = await client.get(
                    f"{self.base_url}/people/match",
                    params={"api_key": self._api_key, "email": email}
                )
                response.raise_for_status()
                result = response.json()
                return {"ok": True, "data": result.get("person")}
            
            else:
                raise ValueError(f"Unsupported data type for Apollo: {data_type}")

    async def search_people(self, query: str) -> List[Dict[str, Any]]:
        """Search people in Apollo"""
        result = await self.get_data("people", query=query)
        return result.get("data", [])

    async def enrich_person(self, email: str) -> Dict[str, Any]:
        """Enrich person by email"""
        result = await self.get_data("enrichment", query=email)
        return result.get("data", {})
