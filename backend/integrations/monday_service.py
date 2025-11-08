import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class MondayService:
    """Monday.com integration service for ATOM platform"""

    def __init__(self):
        self.base_url = "https://api.monday.com/v2"
        self.client_id = os.getenv("MONDAY_CLIENT_ID")
        self.client_secret = os.getenv("MONDAY_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "MONDAY_REDIRECT_URI",
            "http://localhost:3000/api/integrations/monday/callback",
        )

    def get_authorization_url(self, state: str = None) -> str:
        """Generate Monday.com OAuth 2.0 authorization URL"""
        auth_url = "https://auth.monday.com/oauth2/authorize"
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "boards:read boards:write workspaces:read users:read",
            "state": state or "default",
        }
        return f"{auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        token_url = "https://auth.monday.com/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope"),
            }
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        token_url = "https://auth.monday.com/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    def _make_request(
        self, access_token: str, query: str, variables: Dict = None
    ) -> Dict[str, Any]:
        """Make GraphQL request to Monday.com API"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "API-Version": "2023-10",
        }

        payload = {"query": query, "variables": variables or {}}

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Monday.com API request failed: {e}")
            raise

    def get_boards(
        self, access_token: str, workspace_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all boards from Monday.com"""
        query = """
        query GetBoards($workspaceId: ID) {
            boards(workspace_ids: [$workspaceId], limit: 100) {
                id
                name
                description
                board_kind
                updated_at
                workspace_id
                items_count
                columns {
                    id
                    title
                    type
                }
            }
        }
        """

        variables = {}
        if workspace_id:
            variables["workspaceId"] = workspace_id

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("boards", [])

    def get_board(self, access_token: str, board_id: str) -> Dict[str, Any]:
        """Get specific board details"""
        query = """
        query GetBoard($boardId: ID!) {
            boards(ids: [$boardId]) {
                id
                name
                description
                board_kind
                updated_at
                workspace_id
                items_count
                columns {
                    id
                    title
                    type
                }
                items {
                    id
                    name
                    created_at
                    updated_at
                    column_values {
                        id
                        text
                        value
                        type
                    }
                }
            }
        }
        """

        variables = {"boardId": board_id}
        result = self._make_request(access_token, query, variables)
        boards = result.get("data", {}).get("boards", [])
        return boards[0] if boards else {}

    def get_items(
        self, access_token: str, board_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get items from a specific board"""
        query = """
        query GetItems($boardId: ID!, $limit: Int!) {
            boards(ids: [$boardId]) {
                items(limit: $limit) {
                    id
                    name
                    created_at
                    updated_at
                    state
                    column_values {
                        id
                        text
                        value
                        type
                    }
                    creator {
                        id
                        name
                        email
                    }
                }
            }
        }
        """

        variables = {"boardId": board_id, "limit": limit}
        result = self._make_request(access_token, query, variables)
        boards = result.get("data", {}).get("boards", [])
        return boards[0].get("items", []) if boards else []

    def create_item(
        self,
        access_token: str,
        board_id: str,
        item_name: str,
        column_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new item on a board"""
        query = """
        mutation CreateItem($boardId: ID!, $itemName: String!, $columnValues: JSON) {
            create_item(board_id: $boardId, item_name: $itemName, column_values: $columnValues) {
                id
                name
                created_at
            }
        }
        """

        variables = {
            "boardId": board_id,
            "itemName": item_name,
            "columnValues": json.dumps(column_values) if column_values else None,
        }

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("create_item", {})

    def update_item(
        self,
        access_token: str,
        item_id: str,
        column_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update an existing item"""
        query = """
        mutation UpdateItem($itemId: ID!, $columnValues: JSON!) {
            change_multiple_column_values(item_id: $itemId, column_values: $columnValues) {
                id
                name
            }
        }
        """

        variables = {
            "itemId": item_id,
            "columnValues": json.dumps(column_values) if column_values else {},
        }

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("change_multiple_column_values", {})

    def get_workspaces(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all workspaces"""
        query = """
        query GetWorkspaces {
            workspaces {
                id
                name
                description
                kind
                created_at
            }
        }
        """

        result = self._make_request(access_token, query)
        return result.get("data", {}).get("workspaces", [])

    def get_users(
        self, access_token: str, workspace_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get users in workspace"""
        query = """
        query GetUsers($workspaceId: ID) {
            users(kind: non_guests, workspace_id: $workspaceId) {
                id
                name
                email
                title
                created_at
                is_guest
                is_pending
            }
        }
        """

        variables = {}
        if workspace_id:
            variables["workspaceId"] = workspace_id

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("users", [])

    def create_board(
        self,
        access_token: str,
        name: str,
        board_kind: str = "public",
        workspace_id: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new board"""
        query = """
        mutation CreateBoard($name: String!, $boardKind: BoardKind!, $workspaceId: ID, $templateId: ID) {
            create_board(board_name: $name, board_kind: $boardKind, workspace_id: $workspaceId, template_id: $templateId) {
                id
                name
                board_kind
                workspace_id
            }
        }
        """

        variables = {
            "name": name,
            "boardKind": board_kind.upper(),
            "workspaceId": workspace_id,
            "templateId": template_id,
        }

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("create_board", {})

    def get_health_status(self, access_token: str) -> Dict[str, Any]:
        """Check Monday.com service health"""
        try:
            # Simple query to test connectivity
            query = """
            query HealthCheck {
                boards(limit: 1) {
                    id
                    name
                }
            }
            """

            result = self._make_request(access_token, query)
            return {
                "status": "healthy" if result.get("data") else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "details": result,
            }
        except Exception as e:
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    def search_items(
        self, access_token: str, query_term: str, board_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search items across boards"""
        query = """
        query SearchItems($query: String!, $boardIds: [ID]) {
            items(search_query: $query, limit: 50, board_ids: $boardIds) {
                id
                name
                created_at
                updated_at
                board {
                    id
                    name
                }
                column_values {
                    id
                    text
                    value
                    type
                }
            }
        }
        """

        variables = {"query": query_term, "boardIds": board_ids or []}

        result = self._make_request(access_token, query, variables)
        return result.get("data", {}).get("items", [])
