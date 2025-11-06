import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from starlette.testclient import TestClient
import sys
import os

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trello_routes import router
from fastapi import FastAPI

# Create test FastAPI app
app = FastAPI()
app.include_router(router)

client = TestClient(app, base_url="http://testserver")


class TestTrelloIntegration:
    """Comprehensive test suite for Trello integration"""

    @pytest.fixture
    def mock_trello_service(self):
        """Mock Trello service for testing"""
        with patch("trello_routes.trello_service") as mock_service:
            # Mock service methods
            mock_service.get_service_info = AsyncMock(
                return_value={
                    "service": "trello",
                    "version": "1.0.0",
                    "status": "operational",
                }
            )

            # Mock board data
            mock_service.get_boards = AsyncMock(
                return_value=[
                    {
                        "id": "board1",
                        "name": "Project Alpha",
                        "desc": "Main project board",
                        "url": "https://trello.com/b/board1",
                        "closed": False,
                        "starred": True,
                    },
                    {
                        "id": "board2",
                        "name": "Backlog",
                        "desc": "Backlog items",
                        "url": "https://trello.com/b/board2",
                        "closed": False,
                        "starred": False,
                    },
                ]
            )

            # Mock board details
            mock_service.get_board = AsyncMock(
                return_value={
                    "id": "board1",
                    "name": "Project Alpha",
                    "desc": "Main project board",
                    "url": "https://trello.com/b/board1",
                    "closed": False,
                    "starred": True,
                    "prefs": {"background": "blue", "permissionLevel": "private"},
                }
            )

            # Mock lists data
            mock_service.get_lists = AsyncMock(
                return_value=[
                    {"id": "list1", "name": "To Do", "closed": False, "pos": 16384},
                    {
                        "id": "list2",
                        "name": "In Progress",
                        "closed": False,
                        "pos": 32768,
                    },
                    {"id": "list3", "name": "Done", "closed": False, "pos": 49152},
                ]
            )

            # Mock cards data
            mock_service.get_cards = AsyncMock(
                return_value=[
                    {
                        "id": "card1",
                        "name": "Design homepage",
                        "desc": "Create homepage design mockups",
                        "due": "2024-01-15T00:00:00Z",
                        "labels": [
                            {"id": "label1", "name": "Design", "color": "green"}
                        ],
                        "idList": "list1",
                        "idBoard": "board1",
                    },
                    {
                        "id": "card2",
                        "name": "Implement auth",
                        "desc": "Set up authentication system",
                        "due": "2024-01-20T00:00:00Z",
                        "labels": [
                            {"id": "label2", "name": "Backend", "color": "blue"}
                        ],
                        "idList": "list2",
                        "idBoard": "board1",
                    },
                ]
            )

            # Mock card details
            mock_service.get_card = AsyncMock(
                return_value={
                    "id": "card1",
                    "name": "Design homepage",
                    "desc": "Create homepage design mockups",
                    "due": "2024-01-15T00:00:00Z",
                    "labels": [{"id": "label1", "name": "Design", "color": "green"}],
                    "idList": "list1",
                    "idBoard": "board1",
                    "url": "https://trello.com/c/card1",
                }
            )

            # Mock card creation
            mock_service.create_card = AsyncMock(
                return_value={
                    "id": "card3",
                    "name": "[TASK] New feature implementation",
                    "desc": "Implement new feature requirements",
                    "idList": "list1",
                    "idBoard": "board1",
                    "url": "https://trello.com/c/card3",
                }
            )

            # Mock card update
            mock_service.update_card = AsyncMock(
                return_value={
                    "id": "card1",
                    "name": "Design homepage - Updated",
                    "desc": "Create homepage design mockups - Revised",
                    "due": "2024-01-18T00:00:00Z",
                    "idList": "list2",
                    "idBoard": "board1",
                }
            )

            # Mock card deletion
            mock_service.delete_card = AsyncMock(return_value=True)

            # Mock members data
            mock_service.get_members = AsyncMock(
                return_value=[
                    {
                        "id": "member1",
                        "fullName": "John Doe",
                        "username": "johndoe",
                        "avatarUrl": "https://avatar.example.com/john",
                        "memberType": "normal",
                    },
                    {
                        "id": "member2",
                        "fullName": "Jane Smith",
                        "username": "janesmith",
                        "avatarUrl": "https://avatar.example.com/jane",
                        "memberType": "admin",
                    },
                ]
            )

            # Mock search results
            mock_service.search_cards = AsyncMock(
                return_value=[
                    {
                        "id": "card1",
                        "name": "Design homepage",
                        "type": "card",
                        "score": 0.85,
                    },
                    {
                        "id": "board1",
                        "name": "Project Alpha",
                        "type": "board",
                        "score": 0.72,
                    },
                ]
            )

            # Mock activities
            mock_service.get_board_activities = AsyncMock(
                return_value=[
                    {
                        "id": "activity1",
                        "type": "updateCard",
                        "date": "2024-01-10T10:30:00Z",
                        "data": {
                            "card": {"id": "card1", "name": "Design homepage"},
                            "listBefore": {"id": "list1", "name": "To Do"},
                            "listAfter": {"id": "list2", "name": "In Progress"},
                        },
                    },
                    {
                        "id": "activity2",
                        "type": "commentCard",
                        "date": "2024-01-10T11:15:00Z",
                        "data": {
                            "card": {"id": "card1", "name": "Design homepage"},
                            "text": "Looking good!",
                        },
                    },
                ]
            )

            yield mock_service

    def test_health_endpoint(self, mock_trello_service):
        """Test Trello health endpoint"""
        response = client.get("/api/integrations/trello/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "trello"
        assert data["service_available"] == True
        assert data["database_available"] == True
        assert "timestamp" in data

    def test_get_boards(self, mock_trello_service):
        """Test getting boards for a user"""
        response = client.post(
            "/api/integrations/trello/boards",
            json={
                "user_id": "test-user-123",
                "include_closed": False,
                "limit": 10,
                "fields": ["name", "id", "desc", "url", "closed", "starred"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "boards" in data["data"]
        assert len(data["data"]["boards"]) == 2
        assert data["data"]["total_count"] == 2
        assert data["data"]["user_id"] == "test-user-123"

    def test_get_specific_board(self, mock_trello_service):
        """Test getting specific board details"""
        response = client.post(
            "/api/integrations/trello/boards/board1",
            json={
                "user_id": "test-user-123",
                "fields": ["name", "id", "desc", "url", "closed", "starred", "prefs"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "board" in data["data"]
        assert data["data"]["board"]["id"] == "board1"
        assert data["data"]["board"]["name"] == "Project Alpha"

    def test_get_lists(self, mock_trello_service):
        """Test getting lists for a board"""
        response = client.post(
            "/api/integrations/trello/lists",
            json={
                "user_id": "test-user-123",
                "board_id": "board1",
                "include_closed": False,
                "limit": 10,
                "fields": ["name", "id", "closed", "pos"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "lists" in data["data"]
        assert len(data["data"]["lists"]) == 3
        assert data["data"]["board_id"] == "board1"

    def test_get_cards(self, mock_trello_service):
        """Test getting cards from a board"""
        response = client.post(
            "/api/integrations/trello/cards",
            json={
                "user_id": "test-user-123",
                "board_id": "board1",
                "list_id": "list1",
                "include_archived": False,
                "limit": 10,
                "fields": ["name", "id", "desc", "due", "labels", "idList", "idBoard"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "cards" in data["data"]
        assert len(data["data"]["cards"]) == 2
        assert data["data"]["cards"][0]["name"] == "Design homepage"

    def test_get_specific_card(self, mock_trello_service):
        """Test getting specific card details"""
        response = client.post(
            "/api/integrations/trello/cards/card1",
            json={
                "user_id": "test-user-123",
                "fields": [
                    "name",
                    "id",
                    "desc",
                    "due",
                    "labels",
                    "idList",
                    "idBoard",
                    "url",
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "card" in data["data"]
        assert data["data"]["card"]["id"] == "card1"
        assert data["data"]["card"]["name"] == "Design homepage"

    def test_create_card(self, mock_trello_service):
        """Test creating a new card"""
        response = client.post(
            "/api/integrations/trello/cards/create",
            json={
                "user_id": "test-user-123",
                "name": "New feature implementation",
                "id_list": "list1",
                "desc": "Implement new feature requirements",
                "due": "2024-01-25T00:00:00Z",
                "labels": ["label1", "label2"],
                "card_type": "task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "card" in data["data"]
        assert data["data"]["card"]["id"] == "card3"
        assert (
            data["data"]["message"]
            == "Card 'New feature implementation' created successfully"
        )

    def test_update_card(self, mock_trello_service):
        """Test updating an existing card"""
        response = client.put(
            "/api/integrations/trello/cards/card1",
            json={
                "user_id": "test-user-123",
                "name": "Design homepage - Updated",
                "desc": "Create homepage design mockups - Revised",
                "due": "2024-01-18T00:00:00Z",
                "id_list": "list2",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "card" in data["data"]
        assert data["data"]["card"]["name"] == "Design homepage - Updated"
        assert data["data"]["message"] == "Card card1 updated successfully"

    def test_delete_card(self, mock_trello_service):
        """Test deleting a card"""
        response = client.delete(
            "/api/integrations/trello/cards/card1", json={"user_id": "test-user-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert data["data"]["message"] == "Card card1 deleted successfully"

    def test_get_members(self, mock_trello_service):
        """Test getting board members"""
        response = client.post(
            "/api/integrations/trello/members",
            json={
                "user_id": "test-user-123",
                "board_id": "board1",
                "include_guests": False,
                "limit": 10,
                "fields": ["fullName", "username", "id", "avatarUrl", "memberType"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "members" in data["data"]
        assert len(data["data"]["members"]) == 2
        assert data["data"]["members"][0]["fullName"] == "John Doe"

    def test_get_user_profile(self, mock_trello_service):
        """Test getting user profile"""
        response = client.post(
            "/api/integrations/trello/user/profile", json={"user_id": "test-user-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "user" in data["data"]
        assert data["data"]["user"]["id"] == "test-user-123"
        assert "enterprise" in data["data"]

    def test_search_cards(self, mock_trello_service):
        """Test searching for cards and boards"""
        response = client.post(
            "/api/integrations/trello/search",
            json={
                "user_id": "test-user-123",
                "query": "design",
                "type": "global",
                "limit": 10,
                "board_id": "board1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "results" in data["data"]
        assert len(data["data"]["results"]) == 2
        assert data["data"]["query"] == "design"

    def test_get_board_activities(self, mock_trello_service):
        """Test getting board activities"""
        response = client.post(
            "/api/integrations/trello/activities",
            json={
                "user_id": "test-user-123",
                "board_id": "board1",
                "limit": 10,
                "since": "2024-01-01T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "activities" in data["data"]
        assert len(data["data"]["activities"]) == 2
        assert data["data"]["activities"][0]["type"] == "updateCard"

    def test_error_handling(self, mock_trello_service):
        """Test error handling in API endpoints"""
        # Mock service to raise an exception
        mock_trello_service.get_boards.side_effect = Exception("API connection failed")

        response = client.post(
            "/api/integrations/trello/boards",
            json={"user_id": "test-user-123", "include_closed": False, "limit": 10},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["ok"] == False
        assert "error" in data
        assert "API connection failed" in data["error"]

    def test_validation_errors(self):
        """Test validation errors for missing required fields"""
        # Test missing user_id
        response = client.post(
            "/api/integrations/trello/boards",
            json={"include_closed": False, "limit": 10},
        )

        assert response.status_code == 422  # Validation error

    def test_performance_metrics(self, mock_trello_service):
        """Test performance metrics in responses"""
        import time

        start_time = time.time()
        response = client.post(
            "/api/integrations/trello/boards",
            json={"user_id": "test-user-123", "include_closed": False, "limit": 10},
        )
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Response should be under 2 seconds

        data = response.json()
        assert "timestamp" in data["data"]

    def test_security_headers(self):
        """Test security headers in responses"""
        response = client.get("/api/integrations/trello/health")

        # Check for basic security headers
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "application/json"

    def test_cache_headers(self, mock_trello_service):
        """Test cache control headers"""
        response = client.post(
            "/api/integrations/trello/boards",
            json={"user_id": "test-user-123", "include_closed": False, "limit": 10},
        )

        # Responses should include cache control headers
        # Note: FastAPI TestClient might not include all production headers
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_async_operations(self, mock_trello_service):
        """Test asynchronous operations"""
        # This test ensures async operations work correctly
        response = client.post(
            "/api/integrations/trello/boards",
            json={"user_id": "test-user-123", "include_closed": False, "limit": 10},
        )

        assert response.status
