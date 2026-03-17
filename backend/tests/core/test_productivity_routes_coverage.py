"""
Test Coverage for Productivity Routes API
Testing Notion integration endpoints for OAuth and workspace operations
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.username = "testuser"
    return user


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    return db


@pytest.fixture
def mock_notion_service():
    """Mock NotionService."""
    service = Mock()
    service.search_workspace = AsyncMock()
    service.list_databases = AsyncMock()
    service.get_database_schema = AsyncMock()
    service.query_database = AsyncMock()
    service.get_page = AsyncMock()
    service.create_page = AsyncMock()
    service.update_page = AsyncMock()
    service.append_page_blocks = AsyncMock()
    return service


@pytest.fixture
def client(mock_user, mock_db, mock_notion_service):
    """Test client with mocked dependencies."""
    from fastapi import FastAPI
    from api.productivity_routes import router

    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    def override_get_current_user():
        return mock_user

    def override_get_db():
        return mock_db

    from api.productivity_routes import get_db
    from api.oauth_routes import get_current_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    # Patch NotionService
    with patch('api.productivity_routes.NotionService', return_value=mock_notion_service):
        yield TestClient(app)

    app.dependency_overrides.clear()


# ============================================================================
# TestProductivityRoutes - OAuth Endpoints
# ============================================================================

class TestProductivityRoutes:
    """Test productivity routes OAuth endpoints."""

    def test_get_notion_authorization_url_success(self, client, mock_notion_service):
        """Test successful OAuth authorization URL generation."""
        mock_notion_service.get_authorization_url = AsyncMock(
            return_value="https://api.notion.com/v1/oauth/authorize?client_id=test&response_type=code"
        )

        response = client.get("/productivity/integrations/notion/authorize")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "authorization_url" in data
        assert data["provider"] == "notion"

    def test_get_notion_authorization_url_with_custom_redirect(self, client, mock_notion_service):
        """Test OAuth URL generation with custom redirect URI."""
        mock_notion_service.get_authorization_url = AsyncMock(
            return_value="https://api.notion.com/v1/oauth/authorize?redirect_uri=http://custom"
        )

        response = client.get(
            "/productivity/integrations/notion/authorize?redirect_uri=http://custom"
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data

    def test_notion_oauth_callback_success(self, client, mock_notion_service):
        """Test successful OAuth callback with valid code."""
        mock_notion_service.exchange_code_for_tokens = AsyncMock(
            return_value={
                "workspace_id": "workspace_123",
                "workspace_name": "Test Workspace",
                "workspace_icon": "https://example.com/icon.png"
            }
        )

        response = client.get(
            "/productivity/integrations/notion/callback?code=test_auth_code&state=test_state"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workspace_id"] == "workspace_123"
        assert data["workspace_name"] == "Test Workspace"

    def test_notion_oauth_callback_user_denied(self, client):
        """Test OAuth callback when user denies authorization."""
        response = client.get(
            "/productivity/integrations/notion/callback?error=access_denied"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "denied" in data["message"].lower()

    def test_notion_oauth_callback_missing_code(self, client):
        """Test OAuth callback without authorization code."""
        response = client.get("/productivity/integrations/notion/callback")

        assert response.status_code == 422  # Validation error


# ============================================================================
# TestTaskManagement - Notion Workspace Operations
# ============================================================================

class TestTaskManagement:
    """Test Notion workspace operations for task management."""

    def test_search_notion_workspace_success(self, client, mock_notion_service):
        """Test successful workspace search."""
        mock_results = [
            {
                "id": "page_123",
                "title": "Test Page",
                "type": "page",
                "url": "https://notion.so/page_123"
            }
        ]
        mock_notion_service.search_workspace.return_value = mock_results

        response = client.post(
            "/productivity/notion/search",
            json={"query": "test query"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["query"] == "test query"
        assert data["count"] == 1
        assert len(data["results"]) == 1

    def test_search_notion_workspace_empty_query(self, client):
        """Test workspace search with empty query (validation error)."""
        response = client.post(
            "/productivity/notion/search",
            json={"query": ""}
        )

        assert response.status_code == 422  # Validation error

    def test_search_notion_workspace_no_results(self, client, mock_notion_service):
        """Test workspace search with no matching results."""
        mock_notion_service.search_workspace.return_value = []

        response = client.post(
            "/productivity/notion/search",
            json={"query": "nonexistent"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_list_notion_databases_success(self, client, mock_notion_service):
        """Test successful database listing."""
        mock_databases = [
            {
                "id": "db_123",
                "title": "Tasks",
                "description": "Task database",
                "url": "https://notion.so/db_123"
            }
        ]
        mock_notion_service.list_databases.return_value = mock_databases

        response = client.get("/productivity/notion/databases")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert len(data["databases"]) == 1

    def test_list_notion_databases_empty(self, client, mock_notion_service):
        """Test database listing with no databases."""
        mock_notion_service.list_databases.return_value = []

        response = client.get("/productivity/notion/databases")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["databases"] == []

    def test_get_database_schema_success(self, client, mock_notion_service):
        """Test successful database schema retrieval."""
        mock_schema = {
            "properties": {
                "Name": {"type": "title"},
                "Status": {"type": "select"},
                "Date": {"type": "date"}
            }
        }
        mock_notion_service.get_database_schema.return_value = mock_schema

        response = client.get("/productivity/notion/databases/db_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["database_id"] == "db_123"
        assert "schema" in data

    def test_get_database_schema_not_found(self, client, mock_notion_service):
        """Test database schema retrieval for non-existent database."""
        mock_notion_service.get_database_schema.side_effect = HTTPException(
            status_code=404, detail="Database not found"
        )

        response = client.get("/productivity/notion/databases/nonexistent")

        assert response.status_code == 404


# ============================================================================
# TestProductivityAnalytics - Database Query Operations
# ============================================================================

class TestProductivityAnalytics:
    """Test database query and analytics operations."""

    def test_query_database_success(self, client, mock_notion_service):
        """Test successful database query."""
        mock_pages = [
            {
                "id": "page_1",
                "properties": {"Name": "Task 1", "Status": "In Progress"}
            },
            {
                "id": "page_2",
                "properties": {"Name": "Task 2", "Status": "Done"}
            }
        ]
        mock_notion_service.query_database.return_value = mock_pages

        response = client.post(
            "/productivity/notion/databases/db_123/query",
            json={"filter": {"property": "Status", "value": "In Progress"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["database_id"] == "db_123"
        assert data["count"] == 2

    def test_query_database_no_filter(self, client, mock_notion_service):
        """Test database query without filter (returns all pages)."""
        mock_notion_service.query_database.return_value = []

        response = client.post(
            "/productivity/notion/databases/db_123/query",
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_query_database_empty_results(self, client, mock_notion_service):
        """Test database query with no matching results."""
        mock_notion_service.query_database.return_value = []

        response = client.post(
            "/productivity/notion/databases/db_123/query",
            json={"filter": {"property": "Status", "value": "Archived"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_get_page_content_success(self, client, mock_notion_service):
        """Test successful page content retrieval."""
        mock_page = {
            "id": "page_123",
            "properties": {"Name": "Test Page"},
            "blocks": [
                {"type": "paragraph", "content": "Test content"}
            ]
        }
        mock_notion_service.get_page.return_value = mock_page

        response = client.get("/productivity/notion/pages/page_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["page_id"] == "page_123"
        assert "page" in data

    def test_get_page_content_not_found(self, client, mock_notion_service):
        """Test page retrieval for non-existent page."""
        mock_notion_service.get_page.side_effect = HTTPException(
            status_code=404, detail="Page not found"
        )

        response = client.get("/productivity/notion/pages/nonexistent")

        assert response.status_code == 404


# ============================================================================
# TestProductivityErrors - Error Handling
# ============================================================================

class TestProductivityErrors:
    """Test error handling in productivity routes."""

    def test_search_workspace_service_error(self, client, mock_notion_service):
        """Test workspace search with service error."""
        mock_notion_service.search_workspace.side_effect = Exception("Service unavailable")

        response = client.post(
            "/productivity/notion/search",
            json={"query": "test"}
        )

        assert response.status_code == 500

    def test_list_databases_service_error(self, client, mock_notion_service):
        """Test database listing with service error."""
        mock_notion_service.list_databases.side_effect = Exception("Network error")

        response = client.get("/productivity/notion/databases")

        assert response.status_code == 500

    def test_query_database_service_error(self, client, mock_notion_service):
        """Test database query with service error."""
        mock_notion_service.query_database.side_effect = Exception("Query failed")

        response = client.post(
            "/productivity/notion/databases/db_123/query",
            json={}
        )

        assert response.status_code == 500

    def test_create_page_success(self, client, mock_notion_service):
        """Test successful page creation."""
        mock_page = {
            "id": "new_page_123",
            "properties": {"Name": "New Task"}
        }
        mock_notion_service.create_page.return_value = mock_page

        response = client.post(
            "/productivity/notion/pages",
            json={
                "database_id": "db_123",
                "properties": {"Name": "New Task"}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["database_id"] == "db_123"

    def test_update_page_success(self, client, mock_notion_service):
        """Test successful page update."""
        mock_page = {
            "id": "page_123",
            "properties": {"Name": "Updated Task"}
        }
        mock_notion_service.update_page.return_value = mock_page

        response = client.patch(
            "/productivity/notion/pages/page_123",
            json={"properties": {"Status": "Done"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["page_id"] == "page_123"

    def test_append_blocks_success(self, client, mock_notion_service):
        """Test successful block appending."""
        mock_result = {"blocks_added": 2}
        mock_notion_service.append_page_blocks.return_value = mock_result

        response = client.post(
            "/productivity/notion/pages/page_123/blocks",
            json={
                "blocks": [
                    {"type": "paragraph", "content": "New content"},
                    {"type": "heading_1", "content": "Header"}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["page_id"] == "page_123"

    def test_create_page_missing_database_id(self, client):
        """Test page creation without database_id (validation error)."""
        response = client.post(
            "/productivity/notion/pages",
            json={"properties": {"Name": "Task"}}
        )

        assert response.status_code == 422  # Validation error

    def test_append_blocks_empty_list(self, client):
        """Test appending empty blocks list (validation error)."""
        response = client.post(
            "/productivity/notion/pages/page_123/blocks",
            json={"blocks": []}
        )

        assert response.status_code == 422  # Validation error
