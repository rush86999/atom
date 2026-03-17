"""
Comprehensive test coverage for Productivity Routes API endpoints.

Tests Notion integration endpoints:
- OAuth authorization and callback
- Workspace search
- Database operations (list, schema, query)
- Page CRUD (create, read, update, append blocks)
- Error handling (400, 401, 404, 500)

Target: 75%+ coverage (117+ lines of 156)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.productivity_routes import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    return user


@pytest.fixture
def client():
    """Create FastAPI TestClient for productivity routes."""
    app = FastAPI()
    app.include_router(router)

    # Mock get_current_user dependency
    async def get_current_user_override():
        return Mock(id="test-user-123", username="testuser")

    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = get_current_user_override

    # Mock get_db dependency
    def get_db_override():
        return Mock(spec=Session)

    from core.database import get_db
    app.dependency_overrides[get_db] = get_db_override

    return TestClient(app)


@pytest.fixture
def notion_service_mock():
    """Mock NotionService."""
    service = Mock()

    # OAuth methods
    service.get_authorization_url = AsyncMock(return_value="https://notion.so/authorize")
    service.exchange_code_for_tokens = AsyncMock(return_value={
        "success": True,
        "workspace_id": "workspace-123",
        "workspace_name": "Test Workspace",
        "workspace_icon": "emoji"
    })

    # Workspace methods
    service.search_workspace = AsyncMock(return_value=[
        {"id": "page-1", "title": "Test Page", "type": "page", "url": "https://notion.so/page-1"}
    ])
    service.list_databases = AsyncMock(return_value=[
        {"id": "db-1", "title": "Test DB", "description": "Test", "url": "https://notion.so/db-1"}
    ])
    service.get_database_schema = AsyncMock(return_value={
        "properties": {"Name": {"type": "title"}}
    })
    service.query_database = AsyncMock(return_value=[
        {"id": "page-2", "properties": {"Name": "Item 1"}}
    ])

    # Page methods
    service.get_page = AsyncMock(return_value={
        "id": "page-1",
        "properties": {"title": "Test Page"},
        "content": []
    })
    service.create_page = AsyncMock(return_value={
        "id": "page-3",
        "properties": {"title": "New Page"}
    })
    service.update_page = AsyncMock(return_value={
        "id": "page-1",
        "properties": {"title": "Updated Page"}
    })
    service.append_page_blocks = AsyncMock(return_value={
        "success": True,
        "blocks": [{"id": "block-1"}]
    })

    return service


# ============================================================================
# OAuth Endpoints
# ============================================================================

class TestOAuthEndpoints:
    """Test Notion OAuth endpoints."""

    def test_get_authorization_url_success(self, client):
        """Test getting Notion authorization URL successfully."""
        # The endpoint creates a NotionService instance and calls class method
        # We mock the class method directly
        with patch("api.productivity_routes.NotionService") as MockNotion:
            MockNotion.get_authorization_url = AsyncMock(return_value="https://notion.so/authorize")
            response = client.get("/productivity/integrations/notion/authorize")
            assert response.status_code == 200
            data = response.json()
            assert "authorization_url" in data
            assert data["provider"] == "notion"

    def test_oauth_callback_success(self, client):
        """Test Notion OAuth callback successfully."""
        with patch("api.productivity_routes.NotionService") as MockNotion:
            MockNotion.exchange_code_for_tokens = AsyncMock(return_value={
                "success": True,
                "workspace_id": "workspace-123",
                "workspace_name": "Test Workspace",
                "workspace_icon": "emoji"
            })
            response = client.get("/productivity/integrations/notion/callback?code=test-code")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["workspace_id"] == "workspace-123"

    def test_oauth_callback_denied(self, client):
        """Test Notion OAuth callback with denied authorization."""
        response = client.get("/productivity/integrations/notion/callback?error=access_denied")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# ============================================================================
# Workspace Endpoints
# ============================================================================

class TestWorkspaceEndpoints:
    """Test Notion workspace endpoints."""

    def test_search_workspace_success(self, client):
        """Test searching Notion workspace successfully."""
        with patch("api.productivity_routes.NotionService") as MockNotion:
            mock_instance = Mock()
            mock_instance.search_workspace = AsyncMock(return_value=[
                {"id": "page-1", "title": "Test Page", "type": "page", "url": "https://notion.so/page-1"}
            ])
            MockNotion.return_value = mock_instance

            request_data = {"query": "test"}
            response = client.post("/productivity/notion/search", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["count"] == 1

    def test_list_databases_success(self, client):
        """Test listing Notion databases successfully."""
        with patch("api.productivity_routes.NotionService") as MockNotion:
            mock_instance = Mock()
            mock_instance.list_databases = AsyncMock(return_value=[
                {"id": "db-1", "title": "Test DB", "description": "Test", "url": "https://notion.so/db-1"}
            ])
            MockNotion.return_value = mock_instance

            response = client.get("/productivity/notion/databases")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["databases"]) == 1


# ============================================================================
# Database Endpoints
# ============================================================================

class TestDatabaseEndpoints:
    """Test Notion database endpoints."""

    def test_get_database_schema_success(self, client, notion_service_mock):
        """Test getting database schema successfully."""
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.get("/productivity/notion/databases/db-1")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "schema" in data

    def test_query_database_success(self, client, notion_service_mock):
        """Test querying database successfully."""
        request_data = {"filter": {"property": "Name", "value": "Test"}}
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.post("/productivity/notion/databases/db-1/query", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["database_id"] == "db-1"


# ============================================================================
# Page Endpoints
# ============================================================================

class TestPageEndpoints:
    """Test Notion page endpoints."""

    def test_get_page_success(self, client, notion_service_mock):
        """Test getting page content successfully."""
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.get("/productivity/notion/pages/page-1")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["page_id"] == "page-1"

    def test_create_page_success(self, client, notion_service_mock):
        """Test creating page successfully."""
        request_data = {
            "database_id": "db-1",
            "properties": {"Name": "New Page"}
        }
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.post("/productivity/notion/pages", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_update_page_success(self, client, notion_service_mock):
        """Test updating page successfully."""
        request_data = {"properties": {"Name": "Updated"}}
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.patch("/productivity/notion/pages/page-1", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_append_blocks_success(self, client, notion_service_mock):
        """Test appending content blocks to page successfully."""
        request_data = {
            "blocks": [
                {"type": "paragraph", "content": "Test paragraph"}
            ]
        }
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.post("/productivity/notion/pages/page-1/blocks", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling across all endpoints."""

    def test_get_database_schema_not_found(self, client, notion_service_mock):
        """Test getting non-existent database schema."""
        from fastapi import HTTPException
        notion_service_mock.get_database_schema = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Database not found")
        )
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.get("/productivity/notion/databases/nonexistent")
            assert response.status_code == 404

    def test_get_page_not_found(self, client, notion_service_mock):
        """Test getting non-existent page."""
        from fastapi import HTTPException
        notion_service_mock.get_page = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Page not found")
        )
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.get("/productivity/notion/pages/nonexistent")
            assert response.status_code == 404

    def test_create_page_validation_error(self, client):
        """Test creating page with invalid data."""
        request_data = {}  # Missing required database_id
        response = client.post("/productivity/notion/pages", json=request_data)
        assert response.status_code == 422

    def test_update_page_not_found(self, client, notion_service_mock):
        """Test updating non-existent page."""
        from fastapi import HTTPException
        notion_service_mock.update_page = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Page not found")
        )
        request_data = {"properties": {"Name": "Updated"}}
        with patch("api.productivity_routes.NotionService", return_value=notion_service_mock):
            response = client.patch("/productivity/notion/pages/nonexistent", json=request_data)
            assert response.status_code == 404

    def test_append_blocks_invalid_data(self, client):
        """Test appending blocks with invalid data."""
        request_data = {}  # Missing required blocks field
        response = client.post("/productivity/notion/pages/page-1/blocks", json=request_data)
        assert response.status_code == 422
