"""
Confluence Integration Adapter

Provides OAuth-based integration with Atlassian Confluence for knowledge base and wiki management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class ConfluenceAdapter:
    """
    Adapter for Confluence OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Page and blog management
    - Space and content operations
    - Search and attachment handling
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "confluence"
        self.site_url = os.getenv("CONFLUENCE_SITE_URL")
        self.base_url = f"{self.site_url}/wiki/rest/api" if self.site_url else None

        # OAuth credentials from environment
        self.client_id = os.getenv("CONFLUENCE_CLIENT_ID")
        self.client_secret = os.getenv("CONFLUENCE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CONFLUENCE_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Confluence OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Confluence OAuth consent screen
        """
        if not self.site_url or not self.client_id:
            raise ValueError("Confluence site URL and client ID must be configured")

        # Confluence OAuth endpoint
        auth_url = f"{self.site_url}/wiki/rest/oauth2/latest/authorization"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "read:space-content write:space-content search:confluence",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Confluence OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.site_url or not self.client_id or not self.client_secret:
            raise ValueError("Confluence OAuth credentials not configured")

        token_url = f"{self.site_url}/wiki/rest/oauth2/latest/token"

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

                logger.info(f"Successfully obtained Confluence access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Confluence token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Confluence API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.base_url or not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current user info
                response = await client.get(
                    f"{self.base_url}/user/current",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Confluence connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Confluence connection test failed: {e}")
            return False

    async def search_content(self, query: str, limit: int = 10,
                            space_key: str = None, type: str = "page") -> List[Dict[str, Any]]:
        """
        Search Confluence content using CQL (Confluence Query Language).

        Args:
            query: Search query string
            limit: Maximum number of results
            space_key: Space key to limit search
            type: Content type ("page", "blogpost")

        Returns:
            List of content objects
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            # Build CQL query
            cql = f"type={type} and text ~ '{query}'"
            if space_key:
                cql = f"{cql} and space.key = '{space_key}'"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/content/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={
                        "cql": cql,
                        "limit": limit,
                        "expand": "space,version"
                    }
                )
                response.raise_for_status()

                data = response.json()
                contents = data.get("results", [])

                logger.info(f"Confluence search returned {len(contents)} results for workspace {self.workspace_id}")
                return contents

        except Exception as e:
            logger.error(f"Confluence search failed: {e}")
            raise

    async def get_page(self, page_id: str, expand: str = "body.storage,version,space") -> Dict[str, Any]:
        """
        Retrieve a specific Confluence page by ID.

        Args:
            page_id: Confluence page ID
            expand: Comma-separated list of properties to expand

        Returns:
            Page details with content
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/content/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={"expand": expand}
                )
                response.raise_for_status()

                page = response.json()

                logger.info(f"Retrieved Confluence page {page_id} for workspace {self.workspace_id}")
                return page

        except Exception as e:
            logger.error(f"Failed to retrieve Confluence page {page_id}: {e}")
            raise

    async def create_page(self, space_key: str, title: str, content: str,
                         parent_id: str = None) -> Dict[str, Any]:
        """
        Create a new Confluence page.

        Args:
            space_key: Space key
            title: Page title
            content: Page content (storage format)
            parent_id: Parent page ID (optional)

        Returns:
            Created page object
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            # Build page data
            page_data = {
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": content,
                        "representation": "storage"
                    }
                }
            }

            if parent_id:
                page_data["ancestors"] = [{"id": parent_id}]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/content",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=page_data
                )
                response.raise_for_status()

                page = response.json()

                logger.info(f"Created Confluence page {page.get('id')} for workspace {self.workspace_id}")
                return page

        except Exception as e:
            logger.error(f"Failed to create Confluence page: {e}")
            raise

    async def update_page(self, page_id: str, title: str = None,
                         content: str = None, version: int = None) -> Dict[str, Any]:
        """
        Update a Confluence page.

        Args:
            page_id: Page ID to update
            title: New page title
            content: New page content
            version: Version number (must increment)

        Returns:
            Updated page object
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            # Get current page if version not provided
            if version is None:
                current_page = await self.get_page(page_id, expand="version")
                version = current_page.get("version", {}).get("number", 1) + 1

            # Build update data
            update_data = {
                "id": page_id,
                "type": "page",
                "version": {"number": version}
            }

            if title:
                update_data["title"] = title

            if content:
                update_data["body"] = {
                    "storage": {
                        "value": content,
                        "representation": "storage"
                    }
                }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/content/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=update_data
                )
                response.raise_for_status()

                page = response.json()

                logger.info(f"Updated Confluence page {page_id} in workspace {self.workspace_id}")
                return page

        except Exception as e:
            logger.error(f"Failed to update Confluence page {page_id}: {e}")
            raise

    async def delete_page(self, page_id: str) -> bool:
        """
        Delete a Confluence page.

        Args:
            page_id: Page ID to delete

        Returns:
            True if successful
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/content/{page_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Deleted Confluence page {page_id} in workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete Confluence page {page_id}: {e}")
            return False

    async def get_spaces(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve all Confluence spaces.

        Args:
            limit: Maximum number of results

        Returns:
            List of space objects
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/space",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={
                        "limit": limit,
                        "expand": "description"
                    }
                )
                response.raise_for_status()

                data = response.json()
                spaces = data.get("results", [])

                logger.info(f"Retrieved {len(spaces)} Confluence spaces for workspace {self.workspace_id}")
                return spaces

        except Exception as e:
            logger.error(f"Failed to retrieve Confluence spaces: {e}")
            raise

    async def add_comment(self, page_id: str, text: str) -> Dict[str, Any]:
        """
        Add a comment to a Confluence page.

        Args:
            page_id: Page ID
            text: Comment text (storage format)

        Returns:
            Created comment object
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/content/{page_id}/child/comment",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "type": "comment",
                        "body": {
                            "storage": {
                                "value": text,
                                "representation": "storage"
                            }
                        }
                    }
                )
                response.raise_for_status()

                comment = response.json()

                logger.info(f"Added comment to Confluence page {page_id} in workspace {self.workspace_id}")
                return comment

        except Exception as e:
            logger.error(f"Failed to add comment to Confluence page {page_id}: {e}")
            raise

    async def get_attachments(self, page_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve all attachments for a Confluence page.

        Args:
            page_id: Page ID
            limit: Maximum number of results

        Returns:
            List of attachment objects
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/content/{page_id}/child/attachment",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={
                        "limit": limit,
                        "expand": "version"
                    }
                )
                response.raise_for_status()

                data = response.json()
                attachments = data.get("results", [])

                logger.info(f"Retrieved {len(attachments)} attachments for page {page_id}")
                return attachments

        except Exception as e:
            logger.error(f"Failed to retrieve attachments for page {page_id}: {e}")
            raise

    async def get_page_children(self, page_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve all child pages of a Confluence page.

        Args:
            page_id: Parent page ID
            limit: Maximum number of results

        Returns:
            List of child page objects
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Confluence API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/content/{page_id}/child/page",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={
                        "limit": limit,
                        "expand": "version"
                    }
                )
                response.raise_for_status()

                data = response.json()
                children = data.get("results", [])

                logger.info(f"Retrieved {len(children)} child pages for page {page_id}")
                return children

        except Exception as e:
            logger.error(f"Failed to retrieve child pages for {page_id}: {e}")
            raise
