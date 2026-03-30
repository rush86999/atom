"""
Tableau Integration Adapter

Provides OAuth-based integration with Tableau for analytics and data visualization.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class TableauAdapter:
    """
    Adapter for Tableau OAuth integration.

    Supports:
    - OAuth 2.0 authentication (PAT - Personal Access Token)
    - Workbook and data source management
    - Project and view access
    - Query and embedding operations
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "tableau"
        self.base_url = os.getenv("TABLEAU_SERVER_URL", "https://online.tableau.com")

        # OAuth credentials from environment
        self.client_id = os.getenv("TABLEAU_CLIENT_ID")
        self.client_secret = os.getenv("TABLEAU_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TABLEAU_REDIRECT_URI")
        self.pat_name = os.getenv("TABLEAU_PAT_NAME")
        self.pat_secret = os.getenv("TABLEAU_PAT_SECRET")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._site_id: Optional[str] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Tableau OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Tableau OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("TABLEAU_CLIENT_ID not configured")

        # Tableau OAuth endpoint
        auth_url = f"{self.base_url}/oauth/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Tableau OAuth URL for workspace {self.workspace_id}")
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
            raise ValueError("Tableau OAuth credentials not configured")

        token_url = f"{self.base_url}/oauth/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, json=data)
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

                logger.info(f"Successfully obtained Tableau access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Tableau token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Tableau API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token and not self.pat_secret:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting user info
                headers = {}
                if self._access_token:
                    headers["Authorization"] = f"Bearer {self._access_token}"
                elif self.pat_secret:
                    # Use PAT authentication
                    import base64
                    credentials = base64.b64encode(
                        f"{self.pat_name}:{self.pat_secret}".encode()
                    ).decode()
                    headers["X-Tableau-Auth"] = credentials

                response = await client.get(
                    f"{self.base_url}/api/3.17/sites",
                    headers=headers
                )
                response.raise_for_status()

                logger.info(f"Tableau connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Tableau connection test failed: {e}")
            return False

    async def get_workbooks(self, site_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Tableau workbooks.

        Args:
            site_id: Site ID (content URL)

        Returns:
            List of workbook objects
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                import base64
                credentials = base64.b64encode(
                    f"{self.pat_name}:{self.pat_secret}".encode()
                ).decode()
                headers["X-Tableau-Auth"] = credentials

            site = site_id or self._site_id or ""

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/3.17/sites/{site}/workbooks",
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()
                workbooks = data.get("workbook", {}).get("workbook", [])

                # Handle single workbook case
                if isinstance(workbooks, dict):
                    workbooks = [workbooks]

                logger.info(f"Retrieved {len(workbooks)} Tableau workbooks for workspace {self.workspace_id}")
                return workbooks

        except Exception as e:
            logger.error(f"Failed to retrieve Tableau workbooks: {e}")
            raise

    async def get_workbook(self, workbook_id: str, site_id: str = None) -> Dict[str, Any]:
        """
        Retrieve a specific Tableau workbook by ID.

        Args:
            workbook_id: Workbook ID
            site_id: Site ID (content URL)

        Returns:
            Workbook details with all views
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                import base64
                credentials = base64.b64encode(
                    f"{self.pat_name}:{self.pat_secret}".encode()
                ).decode()
                headers["X-Tableau-Auth"] = credentials

            site = site_id or self._site_id or ""

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/3.17/sites/{site}/workbooks/{workbook_id}",
                    headers=headers,
                    params={"includeViews": "true"}
                )
                response.raise_for_status()

                data = response.json()
                workbook = data.get("workbook", {})

                logger.info(f"Retrieved Tableau workbook {workbook_id} for workspace {self.workspace_id}")
                return workbook

        except Exception as e:
            logger.error(f"Failed to retrieve Tableau workbook {workbook_id}: {e}")
            raise

    async def get_views(self, workbook_id: str, site_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve all views in a Tableau workbook.

        Args:
            workbook_id: Workbook ID
            site_id: Site ID (content URL)

        Returns:
            List of view objects
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                import base64
                credentials = base64.b64encode(
                    f"{self.pat_name}:{self.pat_secret}".encode()
                ).decode()
                headers["X-Tableau-Auth"] = credentials

            site = site_id or self._site_id or ""

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/3.17/sites/{site}/workbooks/{workbook_id}/views",
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()
                views = data.get("view", {}).get("view", [])

                # Handle single view case
                if isinstance(views, dict):
                    views = [views]

                logger.info(f"Retrieved {len(views)} Tableau views for workbook {workbook_id}")
                return views

        except Exception as e:
            logger.error(f"Failed to retrieve Tableau views: {e}")
            raise

    async def get_projects(self, site_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve all Tableau projects.

        Args:
            site_id: Site ID (content URL)

        Returns:
            List of project objects
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                import base64
                credentials = base64.b64encode(
                    f"{self.pat_name}:{self.pat_secret}".encode()
                ).decode()
                headers["X-Tableau-Auth"] = credentials

            site = site_id or self._site_id or ""

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/3.17/sites/{site}/projects",
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()
                projects = data.get("project", {}).get("project", [])

                # Handle single project case
                if isinstance(projects, dict):
                    projects = [projects]

                logger.info(f"Retrieved {len(projects)} Tableau projects for workspace {self.workspace_id}")
                return projects

        except Exception as e:
            logger.error(f"Failed to retrieve Tableau projects: {e}")
            raise

    async def query_view_image(self, view_id: str, site_id: str = None) -> str:
        """
        Get the image URL for a Tableau view.

        Args:
            view_id: View ID
            site_id: Site ID (content URL)

        Returns:
            Image URL for the view
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            site = site_id or self._site_id or ""
            image_url = f"{self.base_url}/api/3.17/sites/{site}/views/{view_id}/image"

            if token:
                # Add token as query parameter
                from urllib.parse import urlencode
                image_url = f"{image_url}?{urlencode({'token': token})}"

            logger.info(f"Generated image URL for Tableau view {view_id}")
            return image_url

        except Exception as e:
            logger.error(f"Failed to generate image URL for view {view_id}: {e}")
            raise

    async def get_datasources(self, site_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve all Tableau data sources.

        Args:
            site_id: Site ID (content URL)

        Returns:
            List of data source objects
        """
        token = self._access_token
        if not token and not self.pat_secret:
            raise ValueError("Tableau credentials not configured")

        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                import base64
                credentials = base64.b64encode(
                    f"{self.pat_name}:{self.pat_secret}".encode()
                ).decode()
                headers["X-Tableau-Auth"] = credentials

            site = site_id or self._site_id or ""

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/3.17/sites/{site}/datasources",
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()
                datasources = data.get("datasource", {}).get("datasource", [])

                # Handle single datasource case
                if isinstance(datasources, dict):
                    datasources = [datasources]

                logger.info(f"Retrieved {len(datasources)} Tableau datasources for workspace {self.workspace_id}")
                return datasources

        except Exception as e:
            logger.error(f"Failed to retrieve Tableau datasources: {e}")
            raise
