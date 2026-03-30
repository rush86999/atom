"""
Notion Integration Adapter

Provides OAuth-based integration with Notion for workspace and database access.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NotionAdapter:
    """
    Adapter for Notion OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Database and workspace access
    - Page and block operations
    - User management
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "notion"
        self.base_url = "https://api.notion.com/v1"

        # OAuth credentials from environment
        self.client_id = os.getenv("NOTION_CLIENT_ID")
        self.client_secret = os.getenv("NOTION_CLIENT_SECRET")
        self.redirect_uri = os.getenv("NOTION_REDIRECT_URI")

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

    async def ensure_token(self):
        """Ensure we have a valid access token"""
        if not self._access_token:
            await self._load_token()

    async def get_oauth_url(self) -> str:
        """
        Generate Notion OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Notion OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("NOTION_CLIENT_ID not configured")

        # Notion OAuth endpoint
        auth_url = "https://api.notion.com/v1/oauth/authorize"

        # Build authorization URL with required parameters
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": self.redirect_uri,
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Notion OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, workspace_id, workspace_object, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Notion OAuth credentials not configured")

        token_url = "https://api.notion.com/v1/oauth/token"

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

                # Store access token
                self._access_token = token_data.get("access_token")

                # Calculate token expiration
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Notion access token for workspace {self.workspace_id}")

                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Notion token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Notion API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Notion connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Notion connection test failed: {e}")
            return False

    async def search_pages(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search Notion pages by text content.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of page objects with id, title, parent, etc.
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28"
                    },
                    json={
                        "query": query,
                        "filter": {
                            "value": "page",
                            "property": "object"
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])[:limit]

                logger.info(f"Notion search returned {len(results)} pages for workspace {self.workspace_id}")
                return results

        except Exception as e:
            logger.error(f"Notion search failed: {e}")
            raise

    async def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve content of a specific Notion page.

        Args:
            page_id: Notion page ID

        Returns:
            Page content with blocks and properties
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/blocks/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28"
                    }
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Retrieved Notion page {page_id} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to retrieve Notion page {page_id}: {e}")
            raise

    async def create_page(self, parent_id: str, title: str, content: str) -> Dict[str, Any]:
        """
        Create a new page in Notion.

        Args:
            parent_id: Parent page or database ID
            title: Page title
            content: Page content (blocks)

        Returns:
            Created page object
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            # Create page blocks
            blocks = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": content
                                }
                            }
                        ]
                    }
                }
            ]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/pages",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28"
                    },
                    json={
                        "parent": {"page_id": parent_id},
                        "properties": {
                            "title": {
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": title
                                        }
                                    }
                                ]
                            }
                        },
                        "children": blocks
                    }
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Created Notion page in workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to create Notion page: {e}")
            raise

    async def update_page(self, page_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Notion page.

        Args:
            page_id: Page ID to update
            updates: Dictionary of properties/archived/deleted flags or new content

        Returns:
            Updated page object
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/pages/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28"
                    },
                    json=updates
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Updated Notion page {page_id} in workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to update Notion page {page_id}: {e}")
            raise

    async def delete_page(self, page_id: str) -> bool:
        """
        Delete a Notion page (archive).

        Args:
            page_id: Page ID to delete

        Returns:
            True if successful
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/pages/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28"
                    },
                    json={
                        "archived": True
                    }
                )
                response.raise_for_status()

        except Exception as e:
            logger.error(f"Failed to archive Notion page {page_id}: {e}")
            return False

    async def get_available_schemas(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available database schemas shared with the Notion integration.
        Uses the search API filtered for databases.

        Returns:
            List of database objects with their properties/schemas.
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json"
                    },
                    json={
                        "filter": {
                            "value": "database",
                            "property": "object"
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                logger.info(f"Discovered {len(results)} databases in Notion workspace {self.workspace_id}")
                return results
        except Exception as e:
            logger.error(f"Failed to fetch Notion databases: {e}")
            return []

    async def fetch_records(self, entity_type: str, limit: int = 100, after: Optional[str] = None) -> Dict[str, Any]:
        """
        Query a Notion database for records (pages).
        
        Args:
            entity_type: The ID of the database to query.
            limit: Number of records to fetch.
            after: start_cursor for pagination.
            
        Returns:
            Dictionary with 'results' (list) and 'paging' (dict).
        """
        if not self._access_token:
            raise ValueError("Notion access token not available")

        try:
            json_data = {"page_size": limit}
            if after:
                json_data["start_cursor"] = after

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/databases/{entity_type}/query",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json"
                    },
                    json=json_data
                )
                response.raise_for_status()
                data = response.json()
                
                # Normalize response to match Universal Adapter pattern
                return {
                    "results": data.get("results", []),
                    "paging": {"after": data.get("next_cursor")} if data.get("has_more") else {}
                }
        except Exception as e:
            logger.error(f"Failed to fetch records from Notion database {entity_type}: {e}")
            return {"results": [], "paging": {}}
