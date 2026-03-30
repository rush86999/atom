"""
OneDrive Integration Adapter

Provides OAuth-based integration with Microsoft OneDrive for file storage and sharing.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class OneDriveAdapter:
    """
    Adapter for Microsoft OneDrive OAuth integration.

    Supports:
    - OAuth 2.0 authentication (Microsoft Graph API)
    - File and folder management
    - Sharing and permissions
    - Drive and item operations
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "onedrive"
        self.base_url = "https://graph.microsoft.com/v1.0"

        # OAuth credentials from environment
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Microsoft OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Microsoft OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("MICROSOFT_CLIENT_ID not configured")

        # Microsoft OAuth endpoint
        auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "Files.ReadWrite.All offline_access",
            "state": self.workspace_id,  # Use workspace_id as state
            "response_mode": "query"
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated OneDrive OAuth URL for workspace {self.workspace_id}")
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
            raise ValueError("Microsoft OAuth credentials not configured")

        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

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

                logger.info(f"Successfully obtained OneDrive access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the OneDrive API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting drive info
                response = await client.get(
                    f"{self.base_url}/me/drive",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"OneDrive connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"OneDrive connection test failed: {e}")
            return False

    async def list_files(self, folder_path: str = "") -> List[Dict[str, Any]]:
        """
        List files and folders in OneDrive.

        Args:
            folder_path: Path to folder (empty for root)

        Returns:
            List of file/folder objects
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            # Build URL for children endpoint
            if folder_path:
                url = f"{self.base_url}/me/drive/root:/{folder_path}:/children"
            else:
                url = f"{self.base_url}/me/drive/root/children"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                files = data.get("value", [])

                logger.info(f"Retrieved {len(files)} OneDrive items for workspace {self.workspace_id}")
                return files

        except Exception as e:
            logger.error(f"Failed to list OneDrive files: {e}")
            raise

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific OneDrive file by ID.

        Args:
            file_id: File ID

        Returns:
            File details with metadata
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/drive/items/{file_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                file_data = response.json()

                logger.info(f"Retrieved OneDrive file {file_id} for workspace {self.workspace_id}")
                return file_data

        except Exception as e:
            logger.error(f"Failed to retrieve OneDrive file {file_id}: {e}")
            raise

    async def upload_file(self, file_obj, file_name: str, folder_path: str = "") -> Dict[str, Any]:
        """
        Upload a file to OneDrive.

        Args:
            file_obj: File object to upload
            file_name: Name for the file
            folder_path: Target folder path (empty for root)

        Returns:
            Uploaded file object
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            # Read file content
            file_content = file_obj.read()

            # Build upload URL
            if folder_path:
                url = f"{self.base_url}/me/drive/root:/{folder_path}/{file_name}:/content"
            else:
                url = f"{self.base_url}/me/drive/root:/{file_name}:/content"

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/octet-stream"
                    },
                    content=file_content
                )
                response.raise_for_status()

                file_data = response.json()

                logger.info(f"Uploaded OneDrive file {file_name} for workspace {self.workspace_id}")
                return file_data

        except Exception as e:
            logger.error(f"Failed to upload OneDrive file {file_name}: {e}")
            raise

    async def download_file(self, file_id: str) -> bytes:
        """
        Download a file from OneDrive.

        Args:
            file_id: File ID to download

        Returns:
            File content as bytes
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/drive/items/{file_id}/content",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                content = response.content

                logger.info(f"Downloaded OneDrive file {file_id} for workspace {self.workspace_id}")
                return content

        except Exception as e:
            logger.error(f"Failed to download OneDrive file {file_id}: {e}")
            raise

    async def create_folder(self, folder_name: str, parent_path: str = "") -> Dict[str, Any]:
        """
        Create a new folder in OneDrive.

        Args:
            folder_name: Name for the folder
            parent_path: Parent folder path (empty for root)

        Returns:
            Created folder object
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            # Build URL
            if parent_path:
                url = f"{self.base_url}/me/drive/root:/{parent_path}:/children"
            else:
                url = f"{self.base_url}/me/drive/root/children"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": folder_name,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "rename"
                    }
                )
                response.raise_for_status()

                folder_data = response.json()

                logger.info(f"Created OneDrive folder {folder_name} for workspace {self.workspace_id}")
                return folder_data

        except Exception as e:
            logger.error(f"Failed to create OneDrive folder {folder_name}: {e}")
            raise

    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file or folder from OneDrive.

        Args:
            file_id: File/Folder ID to delete

        Returns:
            True if successful
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/me/drive/items/{file_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Deleted OneDrive file {file_id} in workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete OneDrive file {file_id}: {e}")
            return False

    async def share_file(self, file_id: str, scope: str = "users") -> Dict[str, Any]:
        """
        Create a sharing link for a file.

        Args:
            file_id: File ID to share
            scope: Sharing scope ("view", "edit", "anonymousView", "anonymousEdit")

        Returns:
            Sharing link object
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/drive/items/{file_id}/createLink",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "type": scope,
                        "scope": "anonymous"
                    }
                )
                response.raise_for_status()

                link_data = response.json()

                logger.info(f"Created sharing link for OneDrive file {file_id} in workspace {self.workspace_id}")
                return link_data

        except Exception as e:
            logger.error(f"Failed to create sharing link for file {file_id}: {e}")
            raise

    async def search_files(self, search_query: str) -> List[Dict[str, Any]]:
        """
        Search for files in OneDrive.

        Args:
            search_query: Search query string

        Returns:
            List of matching file objects
        """
        if not self._access_token:
            raise ValueError("OneDrive access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/drive/root/search(q='{search_query}')",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                files = data.get("value", [])

                logger.info(f"OneDrive search returned {len(files)} results for '{search_query}'")
                return files

        except Exception as e:
            logger.error(f"OneDrive file search failed: {e}")
            raise
