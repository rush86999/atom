"""
Trello Integration Adapter

Provides OAuth-based integration with Trello for board and card management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class TrelloAdapter:
    """
    Adapter for Trello OAuth integration.

    Supports:
    - OAuth 1.0a authentication
    - Board and card management
    - List and label operations
    - Member and team access
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "trello"
        self.base_url = "https://api.trello.com/1"

        # OAuth credentials from environment
        self.api_key = os.getenv("TRELLO_API_KEY")
        self.api_secret = os.getenv("TRELLO_API_SECRET")
        self.oauth_token = os.getenv("TRELLO_OAUTH_TOKEN")
        self.oauth_token_secret = os.getenv("TRELLO_OAUTH_TOKEN_SECRET")
        self.redirect_uri = os.getenv("TRELLO_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        self._token_secret: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Trello OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Trello OAuth consent screen
        """
        if not self.api_key:
            raise ValueError("TRELLO_API_KEY not configured")

        # Trello OAuth endpoint
        auth_url = "https://trello.com/1/OuthorizeRequestToken"

        # Build authorization URL with API key
        params = {
            "name": "ATOM SaaS Integration",
            "expiration": "never",
            "scope": "read,write",
            "response_type": "token",
            "key": self.api_key,
            "return_url": self.redirect_uri
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Trello OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, token: str, verifier: str = None) -> Dict[str, Any]:
        """
        Exchange OAuth authorization token for access token.

        Args:
            token: OAuth token from callback
            verifier: OAuth verifier (for OAuth 1.0a flow)

        Returns:
            Token response with oauth_token and oauth_token_secret
        """
        if not self.api_key or not self.api_secret:
            raise ValueError("Trello OAuth credentials not configured")

        # For Trello, the token from the callback is often the final access token
        # If using OAuth 1.0a flow, we need to exchange it

        self._access_token = token
        if verifier:
            self._token_secret = verifier

        token_data = {
            "oauth_token": token,
            "oauth_token_secret": verifier or "token"
        }

        logger.info(f"Successfully obtained Trello access token for workspace {self.workspace_id}")
        return token_data

    async def test_connection(self) -> bool:
        """
        Test the Trello API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token or not self.api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current member info
                response = await client.get(
                    f"{self.base_url}/members/me",
                    params={
                        "key": self.api_key,
                        "token": self._access_token
                    }
                )
                response.raise_for_status()

                logger.info(f"Trello connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Trello connection test failed: {e}")
            return False

    async def search_cards(self, query: str, board_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search Trello cards by name or description.

        Args:
            query: Search query string
            board_id: Optional board ID to limit search
            limit: Maximum number of results

        Returns:
            List of card objects
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query,
                    "modelTypes": "cards",
                    "cards_limit": limit,
                    "card_fields": "name,desc,idList,idBoard,closed,labels",
                    "key": self.api_key,
                    "token": self._access_token
                }

                if board_id:
                    params["idBoards"] = board_id

                response = await client.get(
                    f"{self.base_url}/search",
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                cards = data.get("cards", [])

                logger.info(f"Trello search returned {len(cards)} cards for workspace {self.workspace_id}")
                return cards

        except Exception as e:
            logger.error(f"Trello card search failed: {e}")
            raise

    async def get_card(self, card_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Trello card by ID.

        Args:
            card_id: Trello card ID

        Returns:
            Card details with all fields
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/cards/{card_id}",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        "fields": "name,desc,closed,due",
                        "members": "true",
                        "labels": "true",
                        "checklists": "true"
                    }
                )
                response.raise_for_status()

                card = response.json()

                logger.info(f"Retrieved Trello card {card_id} for workspace {self.workspace_id}")
                return card

        except Exception as e:
            logger.error(f"Failed to retrieve Trello card {card_id}: {e}")
            raise

    async def create_card(self, list_id: str, name: str, description: str = None,
                         due: str = None, labels: List[str] = None) -> Dict[str, Any]:
        """
        Create a new Trello card.

        Args:
            list_id: List ID to add card to
            name: Card name (required)
            description: Card description
            due: Due date (ISO 8601 format)
            labels: List of label colors (green, yellow, orange, red, purple, blue)

        Returns:
            Created card object with ID
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            # Build card data
            card_data = {
                "idList": list_id,
                "name": name,
            }
            if description:
                card_data["desc"] = description
            if due:
                card_data["due"] = due

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        **card_data
                    }
                )
                response.raise_for_status()

                card = response.json()

                # Add labels if provided
                if labels and card.get("id"):
                    for label in labels:
                        try:
                            await client.post(
                                f"{self.base_url}/cards/{card['id']}/labels",
                                params={
                                    "key": self.api_key,
                                    "token": self._access_token,
                                    "color": label
                                }
                            )
                        except:
                            pass  # Ignore label errors

                logger.info(f"Created Trello card {card.get('id')} for workspace {self.workspace_id}")
                return card

        except Exception as e:
            logger.error(f"Failed to create Trello card: {e}")
            raise

    async def update_card(self, card_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Trello card.

        Args:
            card_id: Card ID to update
            updates: Dictionary of fields to update

        Returns:
            Updated card object
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/cards/{card_id}",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        **updates
                    }
                )
                response.raise_for_status()

                card = response.json()

                logger.info(f"Updated Trello card {card_id} in workspace {self.workspace_id}")
                return card

        except Exception as e:
            logger.error(f"Failed to update Trello card {card_id}: {e}")
            raise

    async def get_boards(self) -> List[Dict[str, Any]]:
        """
        Retrieve all Trello boards for the authenticated member.

        Returns:
            List of board objects
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/members/me/boards",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        "fields": "name,closed,pinned",
                        "lists": "open"
                    }
                )
                response.raise_for_status()

                boards = response.json()

                logger.info(f"Retrieved {len(boards)} Trello boards for workspace {self.workspace_id}")
                return boards

        except Exception as e:
            logger.error(f"Failed to retrieve Trello boards: {e}")
            raise

    async def add_comment(self, card_id: str, text: str) -> Dict[str, Any]:
        """
        Add a comment to a Trello card.

        Args:
            card_id: Card ID
            text: Comment text

        Returns:
            Created action (comment) object
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards/{card_id}/actions/comments",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        "text": text
                    }
                )
                response.raise_for_status()

                action = response.json()

                logger.info(f"Added comment to Trello card {card_id} in workspace {self.workspace_id}")
                return action

        except Exception as e:
            logger.error(f"Failed to add comment to Trello card {card_id}: {e}")
            raise

    async def get_lists(self, board_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all lists on a Trello board.

        Args:
            board_id: Board ID

        Returns:
            List of list objects
        """
        if not self._access_token or not self.api_key:
            raise ValueError("Trello API credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/boards/{board_id}/lists",
                    params={
                        "key": self.api_key,
                        "token": self._access_token,
                        "fields": "name,closed,pos"
                    }
                )
                response.raise_for_status()

                lists = response.json()

                logger.info(f"Retrieved {len(lists)} Trello lists for board {board_id}")
                return lists

        except Exception as e:
            logger.error(f"Failed to retrieve Trello lists for board {board_id}: {e}")
            raise
