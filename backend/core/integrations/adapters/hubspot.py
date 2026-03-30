"""
HubSpot Integration Adapter

Provides OAuth-based integration with HubSpot for CRM, marketing, and sales automation.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class HubSpotAdapter:
    """
    Adapter for HubSpot OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Contact and company management
    - Deal and pipeline tracking
    - Marketing automation
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "hubspot"
        self.base_url = "https://api.hubapi.com"

        # OAuth credentials from environment
        self.client_id = os.getenv("HUBSPOT_CLIENT_ID")
        self.client_secret = os.getenv("HUBSPOT_CLIENT_SECRET")
        self.redirect_uri = os.getenv("HUBSPOT_REDIRECT_URI")

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _load_token(self):
        """Load OAuth tokens from database for the current workspace"""
        if not self.db:
            return
            
        from core.models import IntegrationToken
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.workspace_id == self.workspace_id,
            IntegrationToken.provider == self.service_name
        ).first()
        
        if token:
            self._access_token = token.access_token
            self._refresh_token = token.refresh_token
            self._token_expires_at = token.expires_at

    async def refresh_token(self) -> bool:
        """Refresh HubSpot access token using refresh token"""
        if not self._refresh_token:
            return False
            
        token_url = f"{self.base_url}/oauth/v1/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update DB
                if self.db:
                    from core.models import IntegrationToken
                    token = self.db.query(IntegrationToken).filter(
                        IntegrationToken.workspace_id == self.workspace_id,
                        IntegrationToken.provider == self.service_name
                    ).first()
                    if token:
                        token.access_token = self._access_token
                        token.expires_at = self._token_expires_at
                        self.db.commit()
                
                return True
        except Exception as e:
            logger.error(f"HubSpot token refresh failed: {e}")
            return False

    async def ensure_token(self):
        """Ensure we have a valid non-expired access token"""
        if not self._access_token:
            await self._load_token()
            
        if not self._access_token or (self._token_expires_at and self._token_expires_at < datetime.now()):
            # HubSpot tokens expire in 30 mins, but let's refresh if needed
            if self._refresh_token:
                await self.refresh_token()

    async def get_oauth_url(self) -> str:
        """
        Generate HubSpot OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to HubSpot OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("HUBSPOT_CLIENT_ID not configured")

        # HubSpot OAuth endpoint
        auth_url = "https://app.hubspot.com/oauth/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "crm.objects.contacts.read crm.objects.contacts.write "
                     "crm.objects.companies.read crm.objects.companies.write "
                     "crm.objects.deals.read crm.objects.deals.write",
            "response_type": "code",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated HubSpot OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("HubSpot OAuth credentials not configured")

        token_url = f"{self.base_url}/oauth/v1/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained HubSpot access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HubSpot token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the HubSpot API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current user info
                response = await client.get(
                    f"{self.base_url}/crm/v3/owners/defaults",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()

                logger.info(f"HubSpot connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"HubSpot connection test failed: {e}")
            return False

    async def search_contacts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search HubSpot contacts by email or name.

        Args:
            query: Search query (email, name, or company)
            limit: Maximum number of results

        Returns:
            List of contact objects
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                # Use HubSpot search API
                response = await client.post(
                    f"{self.base_url}/crm/v3/objects/contacts/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "CONTAINS_TOKEN",
                                        "value": query
                                    }
                                ]
                            }
                        ],
                        "limit": limit
                    }
                )
                response.raise_for_status()

                data = response.json()
                contacts = data.get("results", [])

                logger.info(f"HubSpot search returned {len(contacts)} contacts for workspace {self.workspace_id}")
                return contacts

        except Exception as e:
            logger.error(f"HubSpot contact search failed: {e}")
            raise

    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific HubSpot contact by ID.

        Args:
            contact_id: HubSpot contact ID

        Returns:
            Contact details with all properties
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    params={"properties": "email,firstname,lastname,company,phone,website"}
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Retrieved HubSpot contact {contact_id} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to retrieve HubSpot contact {contact_id}: {e}")
            raise

    async def create_contact(self, email: str, first_name: str = None, last_name: str = None,
                            company: str = None, **properties) -> Dict[str, Any]:
        """
        Create a new HubSpot contact.

        Args:
            email: Contact email (required)
            first_name: First name
            last_name: Last name
            company: Company name
            **properties: Additional contact properties

        Returns:
            Created contact object with ID
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            # Build properties object
            contact_props = {
                "email": email,
            }
            if first_name:
                contact_props["firstname"] = first_name
            if last_name:
                contact_props["lastname"] = last_name
            if company:
                contact_props["company"] = company
            contact_props.update(properties)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/crm/v3/objects/contacts",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"properties": contact_props}
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Created HubSpot contact {data.get('id')} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            raise

    async def update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a HubSpot contact.

        Args:
            contact_id: Contact ID to update
            properties: Dictionary of properties to update

        Returns:
            Updated contact object
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"properties": properties}
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Updated HubSpot contact {contact_id} in workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to update HubSpot contact {contact_id}: {e}")
            raise

    async def get_deals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve HubSpot deals.

        Args:
            limit: Maximum number of results

        Returns:
            List of deal objects
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/deals",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "limit": limit,
                        "properties": "dealname,amount,dealstage,pipeline,closedate"
                    }
                )
                response.raise_for_status()

                data = response.json()
                deals = data.get("results", [])

                logger.info(f"Retrieved {len(deals)} HubSpot deals for workspace {self.workspace_id}")
                return deals

        except Exception as e:
            logger.error(f"Failed to retrieve HubSpot deals: {e}")
            raise

    async def create_deal(self, deal_name: str, amount: float = None, pipeline: str = "default",
                         stage: str = None, **properties) -> Dict[str, Any]:
        """
        Create a new HubSpot deal.

        Args:
            deal_name: Deal name (required)
            amount: Deal amount
            pipeline: Pipeline identifier
            stage: Deal stage
            **properties: Additional deal properties

        Returns:
            Created deal object with ID
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            # Build properties object
            deal_props = {
                "dealname": deal_name,
            }
            if amount is not None:
                deal_props["amount"] = amount
            if pipeline:
                deal_props["pipeline"] = pipeline
            if stage:
                deal_props["dealstage"] = stage
            deal_props.update(properties)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/crm/v3/objects/deals",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"properties": deal_props}
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Created HubSpot deal {data.get('id')} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to create HubSpot deal: {e}")
            raise

    async def get_available_schemas(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available object schemas for the HubSpot portal.
        Includes Contacts, Companies, Deals, Tickets, and Custom Objects.

        Returns:
            List of schema definition objects.
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/schemas",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                data = response.json()
                schemas = data.get("results", [])
                
                logger.info(f"Discovered {len(schemas)} schemas for HubSpot workspace {self.workspace_id}")
                return schemas
        except Exception as e:
            logger.error(f"Failed to fetch HubSpot schemas: {e}")
            return []

    async def fetch_records(self, entity_type: str, limit: int = 100, after: Optional[str] = None) -> Dict[str, Any]:
        """
        Unified method to fetch records for any HubSpot object type.
        
        Args:
            entity_type: The object type to fetch (e.g., 'contacts', 'deals', '2-12345' for custom objects)
            limit: Page size
            after: Pagination cursor
            
        Returns:
            Dictionary with 'results' (list) and 'paging' (dict).
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        # Standard object names mapping (plural to singular for some endpoints)
        # HubSpot CRM v3 uses plural for standard objects in the URL path
        endpoint_map = {
            "contact": "contacts",
            "company": "companies",
            "deal": "deals",
            "ticket": "tickets"
        }
        
        normalized_type = endpoint_map.get(entity_type.lower(), entity_type)
        
        try:
            params = {"limit": limit}
            if after:
                params["after"] = after
                
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/{normalized_type}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                logger.debug(f"Fetched {len(data.get('results', []))} {normalized_type} from HubSpot")
                return data
        except Exception as e:
            logger.error(f"Failed to fetch {entity_type} from HubSpot: {e}")
            return {"results": [], "paging": {}}
