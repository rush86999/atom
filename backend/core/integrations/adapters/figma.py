"""
Figma Integration Adapter

Provides OAuth-based integration with Figma for design collaboration and file management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class FigmaAdapter:
    """
    Adapter for Figma OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Design file management
    - Team project access
    - Component and style libraries
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "figma"
        self.base_url = "https://api.figma.com"

        # OAuth credentials from environment
        self.client_id = os.getenv("FIGMA_CLIENT_ID")
        self.client_secret = os.getenv("FIGMA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("FIGMA_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Figma OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Figma OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("FIGMA_CLIENT_ID not configured")

        # Figma OAuth endpoint
        auth_url = "https://www.figma.com/oauth"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "file_read file_identity_requests user_email profile_reads",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Figma OAuth URL for workspace {self.workspace_id}")
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
            raise ValueError("Figma OAuth credentials not configured")

        token_url = "https://www.figma.com/api/oauth/token"

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

                logger.info(f"Successfully obtained Figma access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Figma token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Figma API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting user info
                response = await client.get(
                    f"{self.base_url}/v1/me",
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                logger.info(f"Figma connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Figma connection test failed: {e}")
            return False

    async def get_files(self, team_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Figma files.

        Args:
            team_id: Team ID to filter files

        Returns:
            List of file objects
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                if team_id:
                    url = f"{self.base_url}/v1/teams/{team_id}/projects"
                else:
                    url = f"{self.base_url}/v1/me"

                response = await client.get(
                    url,
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                data = response.json()

                # If team projects, get files from each project
                if team_id and "projects" in data:
                    all_files = []
                    for project in data["projects"]:
                        project_files = await self._get_project_files(project["id"])
                        all_files.extend(project_files)
                    return all_files

                logger.info(f"Retrieved Figma files for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to retrieve Figma files: {e}")
            raise

    async def _get_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        """Helper to get files from a project."""
        if not self._access_token:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/projects/{project_id}/files",
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                data = response.json()
                return data.get("files", [])

        except Exception as e:
            logger.debug(f"Failed to get Figma team projects: {e}")
            return []

    async def get_file(self, file_key: str) -> Dict[str, Any]:
        """
        Retrieve a specific Figma file by key.

        Args:
            file_key: File key (from file URL)

        Returns:
            File details with all nodes
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/files/{file_key}",
                    headers={
                        "X-Figma-Token": self._access_token
                    },
                    params={"depth": "none"}  # Get top-level structure only
                )
                response.raise_for_status()

                file_data = response.json()

                logger.info(f"Retrieved Figma file {file_key} for workspace {self.workspace_id}")
                return file_data

        except Exception as e:
            logger.error(f"Failed to retrieve Figma file {file_key}: {e}")
            raise

    async def get_file_nodes(self, file_key: str, node_ids: List[str]) -> Dict[str, Any]:
        """
        Retrieve specific nodes from a Figma file.

        Args:
            file_key: File key
            node_ids: List of node IDs to retrieve

        Returns:
            Node data
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/files/{file_key}/nodes",
                    headers={
                        "X-Figma-Token": self._access_token
                    },
                    params={"ids": ",".join(node_ids)}
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Retrieved {len(node_ids)} nodes from Figma file {file_key}")
                return data

        except Exception as e:
            logger.error(f"Failed to retrieve Figma nodes: {e}")
            raise

    async def get_components(self, file_key: str) -> List[Dict[str, Any]]:
        """
        Retrieve all components from a Figma file.

        Args:
            file_key: File key

        Returns:
            List of component objects
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/files/{file_key}/components",
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                data = response.json()
                components = data.get("meta", {}).get("components", [])

                logger.info(f"Retrieved {len(components)} Figma components from file {file_key}")
                return components

        except Exception as e:
            logger.error(f"Failed to retrieve Figma components: {e}")
            raise

    async def get_comments(self, file_key: str) -> List[Dict[str, Any]]:
        """
        Retrieve all comments from a Figma file.

        Args:
            file_key: File key

        Returns:
            List of comment objects
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/files/{file_key}/comments",
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                comments = response.json()

                logger.info(f"Retrieved Figma comments from file {file_key}")
                return comments

        except Exception as e:
            logger.error(f"Failed to retrieve Figma comments: {e}")
            raise

    async def post_comment(self, file_key: str, message: str,
                          client_id: str = None, node_id: str = None) -> Dict[str, Any]:
        """
        Post a comment to a Figma file.

        Args:
            file_key: File key
            message: Comment message
            client_id: Unique client ID
            node_id: Node ID to attach comment to

        Returns:
            Created comment object
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            comment_data = {
                "message": message,
                "client_id": client_id or f"{self.workspace_id}_{datetime.now().timestamp()}"
            }

            if node_id:
                comment_data["node_id"] = node_id

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/files/{file_key}/comments",
                    headers={
                        "X-Figma-Token": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json=comment_data
                )
                response.raise_for_status()

                comment = response.json()

                logger.info(f"Posted comment to Figma file {file_key} for workspace {self.workspace_id}")
                return comment

        except Exception as e:
            logger.error(f"Failed to post comment to Figma file: {e}")
            raise

    async def get_teams(self) -> List[Dict[str, Any]]:
        """
        Retrieve all Figma teams for the authenticated user.

        Returns:
            List of team objects
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/me",
                    headers={
                        "X-Figma-Token": self._access_token}
                )
                response.raise_for_status()

                data = response.json()

                # Extract teams from user profile
                teams = data.get("teams", [])

                logger.info(f"Retrieved {len(teams)} Figma teams for workspace {self.workspace_id}")
                return teams

        except Exception as e:
            logger.error(f"Failed to retrieve Figma teams: {e}")
            raise

    async def get_projects(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all projects in a Figma team.

        Args:
            team_id: Team ID

        Returns:
            List of project objects
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/teams/{team_id}/projects",
                    headers={
                        "X-Figma-Token": self._access_token
                    }
                )
                response.raise_for_status()

                data = response.json()
                projects = data.get("projects", [])

                logger.info(f"Retrieved {len(projects)} Figma projects for team {team_id}")
                return projects

        except Exception as e:
            logger.error(f"Failed to retrieve Figma projects: {e}")
            raise

    async def get_image(self, file_key: str, node_ids: List[str] = None,
                       format: str = "png", scale: int = 1) -> Dict[str, Any]:
        """
        Get image export URLs for Figma nodes.

        Args:
            file_key: File key
            node_ids: List of node IDs (empty for entire file)
            format: Image format ("png", "jpg", "svg", "pdf")
            scale: Export scale factor

        Returns:
            Dictionary with image URLs
        """
        if not self._access_token:
            raise ValueError("Figma access token not available")

        try:
            params = {
                "format": format,
                "scale": scale
            }

            if node_ids:
                params["ids"] = ",".join(node_ids)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/images/{file_key}",
                    headers={
                        "X-Figma-Token": self._access_token
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Generated image URLs for Figma file {file_key}")
                return data

        except Exception as e:
            logger.error(f"Failed to generate Figma image URLs: {e}")
            raise
