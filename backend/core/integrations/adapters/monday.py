"""
Monday.com Integration Adapter

Provides OAuth-based integration with Monday.com for work management and collaboration.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class MondayAdapter:
    """
    Adapter for Monday.com OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Board and item management
    - Group and column operations
    - Update and notification access
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "monday"
        self.base_url = "https://api.monday.com/v2"

        # OAuth credentials from environment
        self.client_id = os.getenv("MONDAY_CLIENT_ID")
        self.client_secret = os.getenv("MONDAY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("MONDAY_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Monday.com OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Monday.com OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("MONDAY_CLIENT_ID not configured")

        # Monday.com OAuth endpoint
        auth_url = "https://auth.monday.com/oauth2/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Monday.com OAuth URL for workspace {self.workspace_id}")
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
            raise ValueError("Monday.com OAuth credentials not configured")

        token_url = "https://auth.monday.com/oauth2/token"

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

                logger.info(f"Successfully obtained Monday.com access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Monday.com token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Monday.com API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting user info
                query = """
                    query {
                        users {
                            name
                            email
                        }
                    }
                """

                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={"query": query}
                )
                response.raise_for_status()

                logger.info(f"Monday.com connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Monday.com connection test failed: {e}")
            return False

    async def get_boards(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve all Monday.com boards.

        Args:
            limit: Maximum number of results

        Returns:
            List of board objects
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            query = """
                query($limit: Int!) {
                    boards(limit: $limit) {
                        id
                        name
                        description
                        state
                        columns {
                            id
                            title
                            type
                        }
                    }
                }
            """

            variables = {"limit": limit}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": query,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                boards = data.get("data", {}).get("boards", [])

                logger.info(f"Retrieved {len(boards)} Monday.com boards for workspace {self.workspace_id}")
                return boards

        except Exception as e:
            logger.error(f"Failed to retrieve Monday.com boards: {e}")
            raise

    async def get_items(self, board_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve items from a Monday.com board.

        Args:
            board_id: Board ID
            limit: Maximum number of results

        Returns:
            List of item objects
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            query = """
                query($boardId: ID!, $limit: Int!) {
                    boards(ids: [$boardId]) {
                        items(limit: $limit) {
                            id
                            name
                            state
                            column_values {
                                id
                                text
                                value
                            }
                            updated_at
                        }
                    }
                }
            """

            variables = {"boardId": board_id, "limit": limit}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": query,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                boards = data.get("data", {}).get("boards", [])
                items = boards[0].get("items", []) if boards else []

                logger.info(f"Retrieved {len(items)} Monday.com items for board {board_id}")
                return items

        except Exception as e:
            logger.error(f"Failed to retrieve Monday.com items: {e}")
            raise

    async def get_item(self, item_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Monday.com item by ID.

        Args:
            item_id: Item ID

        Returns:
            Item details with all fields
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            query = """
                query($itemId: ID!) {
                    items(ids: [$itemId]) {
                        id
                        name
                        state
                        board {
                            id
                            name
                        }
                        group {
                            id
                            title
                        }
                        column_values {
                            id
                            title
                            text
                            value
                        }
                        updated_at
                    }
                }
            """

            variables = {"itemId": item_id}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": query,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                items = data.get("data", {}).get("items", [])
                item = items[0] if items else None

                if item:
                    logger.info(f"Retrieved Monday.com item {item_id} for workspace {self.workspace_id}")
                return item

        except Exception as e:
            logger.error(f"Failed to retrieve Monday.com item {item_id}: {e}")
            raise

    async def create_item(self, board_id: str, group_id: str, item_name: str,
                         column_values: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new Monday.com item.

        Args:
            board_id: Board ID
            group_id: Group ID to add item to
            item_name: Item name (required)
            column_values: Column values (format: {"column_id": "value"})

        Returns:
            Created item object with ID
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            mutation = """
                mutation($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
                    create_item(
                        board_id: $boardId
                        group_id: $groupId
                        item_name: $itemName
                        column_values: $columnValues
                    ) {
                        id
                        name
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            """

            variables = {
                "boardId": board_id,
                "groupId": group_id,
                "itemName": item_name,
                "columnValues": column_values or {}
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                item = data.get("data", {}).get("create_item")

                logger.info(f"Created Monday.com item {item.get('id')} for workspace {self.workspace_id}")
                return item

        except Exception as e:
            logger.error(f"Failed to create Monday.com item: {e}")
            raise

    async def update_item(self, item_id: str, column_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Monday.com item.

        Args:
            item_id: Item ID to update
            column_values: Column values to update

        Returns:
            Updated item object
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            mutation = """
                mutation($itemId: ID!, $columnValues: JSON!) {
                    change_multiple_column_values(
                        item_id: $itemId
                        column_values: $columnValues
                    ) {
                        id
                        name
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            """

            variables = {
                "itemId": item_id,
                "columnValues": column_values
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                item = data.get("data", {}).get("change_multiple_column_values")

                logger.info(f"Updated Monday.com item {item_id} in workspace {self.workspace_id}")
                return item

        except Exception as e:
            logger.error(f"Failed to update Monday.com item {item_id}: {e}")
            raise

    async def add_update(self, item_id: str, text: str) -> Dict[str, Any]:
        """
        Add an update (comment) to a Monday.com item.

        Args:
            item_id: Item ID
            text: Update text (supports Markdown)

        Returns:
            Created update object
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            mutation = """
                mutation($itemId: ID!, $text: String!) {
                    create_update(item_id: $itemId, body: $text) {
                        id
                        body
                        created_at
                        updated_at
                    }
                }
            """

            variables = {
                "itemId": item_id,
                "text": text
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                update = data.get("data", {}).get("create_update")

                logger.info(f"Added update to Monday.com item {item_id} in workspace {self.workspace_id}")
                return update

        except Exception as e:
            logger.error(f"Failed to add update to Monday.com item {item_id}: {e}")
            raise

    async def get_groups(self, board_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all groups in a Monday.com board.

        Args:
            board_id: Board ID

        Returns:
            List of group objects
        """
        if not self._access_token:
            raise ValueError("Monday.com access token not available")

        try:
            query = """
                query($boardId: ID!) {
                    boards(ids: [$boardId]) {
                        groups {
                            id
                            title
                            color
                            position
                        }
                    }
                }
            """

            variables = {"boardId": board_id}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": self._access_token,
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": query,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                boards = data.get("data", {}).get("boards", [])
                groups = boards[0].get("groups", []) if boards else []

                logger.info(f"Retrieved {len(groups)} Monday.com groups for board {board_id}")
                return groups

        except Exception as e:
            logger.error(f"Failed to retrieve Monday.com groups: {e}")
            raise
