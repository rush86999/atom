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

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

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

    async def get_companies(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve HubSpot companies.

        Args:
            limit: Maximum number of results

        Returns:
            List of company objects
        """
        if not self._access_token:
            raise ValueError("HubSpot access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/companies",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "limit": limit,
                        "properties": "name,domain,industry,description,phone"
                    }
                )
                response.raise_for_status()

                data = response.json()
                companies = data.get("results", [])

                logger.info(f"Retrieved {len(companies)} HubSpot companies for workspace {self.workspace_id}")
                return companies

        except Exception as e:
            logger.error(f"Failed to retrieve HubSpot companies: {e}")
            raise
