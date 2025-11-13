"""
Monday.com Integration Test

This test file verifies the Monday.com integration service and API routes.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.integrations.monday_routes import monday_router
from backend.integrations.monday_service import MondayService

# Mock data for testing
MOCK_BOARDS = [
    {
        "id": "12345",
        "name": "Test Board",
        "description": "Test board description",
        "board_kind": "public",
        "updated_at": "2024-01-15T10:00:00Z",
        "workspace_id": "workspace_123",
        "items_count": 10,
        "columns": [
            {"id": "col1", "title": "Status", "type": "status"},
            {"id": "col2", "title": "Text", "type": "text"},
        ],
    }
]

MOCK_ITEMS = [
    {
        "id": "item_123",
        "name": "Test Item",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
        "state": "active",
        "column_values": [
            {
                "id": "col1",
                "text": "Working on it",
                "value": "working_on_it",
                "type": "status",
            }
        ],
    }
]

MOCK_WORKSPACES = [
    {
        "id": "workspace_123",
        "name": "Test Workspace",
        "description": "Test workspace description",
        "kind": "open",
        "created_at": "2024-01-15T10:00:00Z",
    }
]

MOCK_USERS = [
    {
        "id": "user_123",
        "name": "Test User",
        "email": "test@example.com",
        "title": "Developer",
        "created_at": "2024-01-15T10:00:00Z",
        "is_guest": False,
        "is_pending": False,
    }
]

MOCK_TOKEN_RESPONSE = {
    "access_token": "mock_access_token_123",
    "refresh_token": "mock_refresh_token_123",
    "expires_in": 3600,
    "token_type": "bearer",
    "scope": "boards:read boards:write",
}


class TestMondayService:
    """Test Monday.com service functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = MondayService()
        self.access_token = "test_access_token"

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_boards_success(self, mock_post):
        """Test successful board retrieval"""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"boards": MOCK_BOARDS}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        boards = self.service.get_boards(self.access_token)

        assert len(boards) == 1
        assert boards[0]["name"] == "Test Board"
        assert boards[0]["items_count"] == 10
        mock_post.assert_called_once()

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_boards_with_workspace(self, mock_post):
        """Test board retrieval with workspace filter"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"boards": MOCK_BOARDS}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        workspace_id = "workspace_123"
        boards = self.service.get_boards(self.access_token, workspace_id)

        assert len(boards) == 1
        # Verify workspace filter was applied in query
        call_args = mock_post.call_args
        assert "workspace_ids" in str(call_args)

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_board_details(self, mock_post):
        """Test specific board details retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"boards": [MOCK_BOARDS[0]]}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        board_id = "12345"
        board = self.service.get_board(self.access_token, board_id)

        assert board["id"] == board_id
        assert board["name"] == "Test Board"
        assert len(board["columns"]) == 2

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_items(self, mock_post):
        """Test item retrieval from board"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"boards": [{"items": MOCK_ITEMS}]}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        board_id = "12345"
        items = self.service.get_items(self.access_token, board_id, limit=50)

        assert len(items) == 1
        assert items[0]["name"] == "Test Item"
        assert items[0]["state"] == "active"

    @patch("backend.integrations.monday_service.requests.post")
    def test_create_item(self, mock_post):
        """Test item creation"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"create_item": MOCK_ITEMS[0]}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        board_id = "12345"
        item_name = "New Test Item"
        column_values = {"status": "working_on_it"}

        result = self.service.create_item(
            self.access_token, board_id, item_name, column_values
        )

        assert result["id"] == "item_123"
        assert result["name"] == "Test Item"
        mock_post.assert_called_once()

    @patch("backend.integrations.monday_service.requests.post")
    def test_update_item(self, mock_post):
        """Test item update"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "change_multiple_column_values": {
                    "id": "item_123",
                    "name": "Updated Item",
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        item_id = "item_123"
        column_values = {"status": "done"}

        result = self.service.update_item(self.access_token, item_id, column_values)

        assert result["id"] == "item_123"
        assert result["name"] == "Updated Item"

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_workspaces(self, mock_post):
        """Test workspace retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"workspaces": MOCK_WORKSPACES}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        workspaces = self.service.get_workspaces(self.access_token)

        assert len(workspaces) == 1
        assert workspaces[0]["name"] == "Test Workspace"
        assert workspaces[0]["kind"] == "open"

    @patch("backend.integrations.monday_service.requests.post")
    def test_get_users(self, mock_post):
        """Test user retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"users": MOCK_USERS}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        users = self.service.get_users(self.access_token)

        assert len(users) == 1
        assert users[0]["name"] == "Test User"
        assert users[0]["email"] == "test@example.com"
        assert users[0]["is_guest"] is False

    @patch("backend.integrations.monday_service.requests.post")
    def test_create_board(self, mock_post):
        """Test board creation"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "create_board": {
                    "id": "new_board_123",
                    "name": "New Board",
                    "board_kind": "public",
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        board_name = "New Board"
        board_kind = "public"

        result = self.service.create_board(self.access_token, board_name, board_kind)

        assert result["id"] == "new_board_123"
        assert result["name"] == "New Board"
        assert result["board_kind"] == "public"

    @patch("backend.integrations.monday_service.requests.post")
    def test_search_items(self, mock_post):
        """Test item search"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"items": MOCK_ITEMS}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        query = "test query"
        board_ids = ["12345"]

        results = self.service.search_items(self.access_token, query, board_ids)

        assert len(results) == 1
        assert results[0]["name"] == "Test Item"

    @patch("backend.integrations.monday_service.requests.post")
    def test_health_check_success(self, mock_post):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"boards": [{"id": "123", "name": "Test Board"}]}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        health_status = self.service.get_health_status(self.access_token)

        assert health_status["status"] == "healthy"
        assert "timestamp" in health_status

    @patch("backend.integrations.monday_service.requests.post")
    def test_health_check_failure(self, mock_post):
        """Test failed health check"""
        mock_post.side_effect = Exception("API Error")

        health_status = self.service.get_health_status(self.access_token)

        assert health_status["status"] == "error"
        assert "API Error" in health_status["error"]

    def test_get_authorization_url(self):
        """Test authorization URL generation"""
        with patch.dict(
            os.environ,
            {
                "MONDAY_CLIENT_ID": "test_client_id",
                "MONDAY_REDIRECT_URI": "http://localhost:3000/callback",
            },
        ):
            service = MondayService()
            auth_url = service.get_authorization_url("test_state")

            assert "auth.monday.com" in auth_url
            assert "test_client_id" in auth_url
            assert "test_state" in auth_url
            assert "boards:read" in auth_url

    @patch("backend.integrations.monday_service.requests.post")
    def test_exchange_code_for_token(self, mock_post):
        """Test token exchange"""
        mock_response = Mock()
        mock_response.json.return_value = MOCK_TOKEN_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {
                "MONDAY_CLIENT_ID": "test_client_id",
                "MONDAY_CLIENT_SECRET": "test_secret",
                "MONDAY_REDIRECT_URI": "http://localhost:3000/callback",
            },
        ):
            service = MondayService()
            token_data = service.exchange_code_for_token("test_code")

            assert token_data["access_token"] == "mock_access_token_123"
            assert token_data["refresh_token"] == "mock_refresh_token_123"
            assert token_data["expires_in"] == 3600

    @patch("backend.integrations.monday_service.requests.post")
    def test_refresh_access_token(self, mock_post):
        """Test token refresh"""
        mock_response = Mock()
        mock_response.json.return_value = MOCK_TOKEN_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {
                "MONDAY_CLIENT_ID": "test_client_id",
                "MONDAY_CLIENT_SECRET": "test_secret",
            },
        ):
            service = MondayService()
            token_data = service.refresh_access_token("refresh_token_123")

            assert token_data["access_token"] == "mock_access_token_123"
            mock_post.assert_called_once()


class TestMondayRoutes:
    """Test Monday.com API routes"""

    def setup_method(self):
        """Set up test client"""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(monday_router)
        self.client = TestClient(app)

    def test_health_endpoint_success(self):
        """Test health endpoint with valid token"""
        with patch(
            "backend.integrations.monday_routes.MondayService.get_health_status"
        ) as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "timestamp": "2024-01-15T10:00:00Z",
                "details": {"boards": []},
            }

            response = self.client.get(
                "/monday/health", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_health_endpoint_missing_token(self):
        """Test health endpoint without token"""
        response = self.client.get("/monday/health")

        assert response.status_code == 401
        assert "Authorization header" in response.json()["detail"]

    def test_get_boards_endpoint(self):
        """Test boards endpoint"""
        with patch(
            "backend.integrations.monday_routes.MondayService.get_boards"
        ) as mock_boards:
            mock_boards.return_value = MOCK_BOARDS

            response = self.client.get(
                "/monday/boards", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "boards" in data
            assert len(data["boards"]) == 1

    def test_get_board_details_endpoint(self):
        """Test specific board endpoint"""
        with patch(
            "backend.integrations.monday_routes.MondayService.get_board"
        ) as mock_board:
            mock_board.return_value = MOCK_BOARDS[0]

            response = self.client.get(
                "/monday/boards/12345", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["board"]["id"] == "12345"

    def test_get_board_not_found(self):
        """Test board not found"""
        with patch(
            "backend.integrations.monday_routes.MondayService.get_board"
        ) as mock_board:
            mock_board.return_value = None

            response = self.client.get(
                "/monday/boards/99999", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_create_item_endpoint(self):
        """Test item creation endpoint"""
        with patch(
            "backend.integrations.monday_routes.MondayService.create_item"
        ) as mock_create:
            mock_create.return_value = MOCK_ITEMS[0]

            response = self.client.post(
                "/monday/boards/12345/items",
                headers={"Authorization": "Bearer test_token"},
                json={
                    "board_id": "12345",
                    "name": "New Item",
                    "column_values": {"status": "working_on_it"},
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert "item" in data
            assert data["item"]["id"] == "item_123"

    def test_create_item_missing_name(self):
        """Test item creation with missing name"""
        response = self.client.post(
            "/monday/boards/12345/items",
            headers={"Authorization": "Bearer test_token"},
            json={"board_id": "12345"},
        )

        assert response.status_code == 422  # Validation error

    def test_search_endpoint(self):
        """Test search endpoint"""
        with patch(
            "backend.integrations.monday_routes.MondayService.search_items"
        ) as mock_search:
            mock_search.return_value = MOCK_ITEMS

            response = self.client.get(
                "/monday/search",
                headers={"Authorization": "Bearer test_token"},
                params={"query": "test query"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) == 1

    def test_search_missing_query(self):
        """Test search without query"""
        response = self.client.get(
            "/monday/search", headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 422  # Validation error


def test_integration_complete():
    """Integration test to verify complete functionality"""
    # This would be an end-to-end test with actual API calls
    # For now, we'll verify the service can be instantiated
    service = MondayService()
    assert service is not None
    assert hasattr(service, "get_boards")
    assert hasattr(service, "create_item")
    assert hasattr(service, "get_health_status")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
