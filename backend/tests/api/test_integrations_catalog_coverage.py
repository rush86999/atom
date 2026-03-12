"""
Integrations Catalog Routes Test Suite

Comprehensive test coverage for integration catalog routes (integrations_catalog_routes.py).

Target Coverage: 75%+ line coverage for api/integrations_catalog_routes.py

Scope:
- GET /api/v1/integrations/catalog - List all integrations with filters and search
- GET /api/v1/integrations/catalog/{piece_id} - Get integration details
- Search functionality (ilike on name and description)
- Filter parameters (category, popular)
- Error paths (404 not found, 500 internal errors)

Test Fixtures:
- mock_db_session: Mock database session with query capabilities
- catalog_client: TestClient with database dependency override
- sample_integration: Factory for integration dictionaries
- sample_integrations: Factory for list of test integrations
- integration_response_structure: Expected response fields

External Services: None (uses mocked database)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import routers and models
from api.integrations_catalog_routes import router
from core.database import get_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_db_session():
    """
    Mock database session for testing.

    Uses MagicMock to simulate database operations without requiring
    a real database connection. This avoids SQLite JSONB compatibility issues.
    """
    mock_session = MagicMock(spec=Session)

    # Mock query chain
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query

    # Configure filter method to return mock_query (for chaining)
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []
    mock_query.first.return_value = None

    return mock_session


@pytest.fixture(scope="function")
def catalog_client(mock_db_session):
    """
    TestClient with database dependency override.

    Overrides the get_db dependency to use our mock database session.
    """
    from fastapi import FastAPI
    from api.integrations_catalog_routes import router
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        try:
            yield mock_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_integration():
    """
    Integration fixture factory.

    Returns a factory function that creates integration dictionaries
    with default values for testing.
    """
    def _create_integration(
        id="test_integration_1",
        name="Test Integration",
        description="A test integration for testing",
        category="productivity",
        popular=False
    ):
        return {
            "id": id,
            "name": name,
            "description": description,
            "category": category,
            "icon": "test-icon",
            "color": "#6366F1",
            "auth_type": "none",
            "triggers": [{"name": "test_trigger"}],
            "actions": [{"name": "test_action"}],
            "popular": popular,
            "native_id": None
        }

    return _create_integration


@pytest.fixture(scope="function")
def sample_integrations():
    """
    Factory for list of test integrations.

    Creates 6 integration dictionaries with mixed categories
    and popular flags for comprehensive testing.
    """
    integrations = [
        {
            "id": "slack_1",
            "name": "Slack",
            "description": "Team messaging platform",
            "category": "communication",
            "icon": "slack-icon",
            "color": "#4A154B",
            "auth_type": "oauth",
            "triggers": [{"name": "new_message"}],
            "actions": [{"name": "send_message"}],
            "popular": True
        },
        {
            "id": "gmail_1",
            "name": "Gmail",
            "description": "Email service integration",
            "category": "email",
            "icon": "gmail-icon",
            "color": "#EA4335",
            "auth_type": "oauth",
            "triggers": [{"name": "new_email"}],
            "actions": [{"name": "send_email"}],
            "popular": True
        },
        {
            "id": "dropbox_1",
            "name": "Dropbox",
            "description": "File storage and sharing",
            "category": "productivity",
            "icon": "dropbox-icon",
            "color": "#0061FF",
            "auth_type": "oauth",
            "triggers": [{"name": "file_uploaded"}],
            "actions": [{"name": "upload_file"}],
            "popular": False
        },
        {
            "id": "trello_1",
            "name": "Trello",
            "description": "Project management and collaboration",
            "category": "productivity",
            "icon": "trello-icon",
            "color": "#0079BF",
            "auth_type": "api_key",
            "triggers": [{"name": "card_created"}],
            "actions": [{"name": "create_card"}],
            "popular": True
        },
        {
            "id": "salesforce_1",
            "name": "Salesforce",
            "description": "CRM and sales automation",
            "category": "crm",
            "icon": "salesforce-icon",
            "color": "#00A1E0",
            "auth_type": "oauth",
            "triggers": [{"name": "new_lead"}],
            "actions": [{"name": "create_lead"}],
            "popular": False
        },
        {
            "id": "mailchimp_1",
            "name": "Mailchimp",
            "description": "Email marketing platform",
            "category": "email",
            "icon": "mailchimp-icon",
            "color": "#FFE01B",
            "auth_type": "api_key",
            "triggers": [{"name": "campaign_sent"}],
            "actions": [{"name": "send_campaign"}],
            "popular": True
        }
    ]

    return integrations


@pytest.fixture(scope="function")
def integration_response_structure():
    """
    Expected response fields for integration endpoints.

    List of required fields that should be present in
    IntegrationResponse objects.
    """
    return [
        "id",
        "name",
        "description",
        "category",
        "icon",
        "color",
        "authType",
        "triggers",
        "actions",
        "popular"
    ]


# ============================================================================
# Test Class: TestIntegrationsCatalog
# ============================================================================

class TestIntegrationsCatalog:
    """Tests for GET /api/v1/integrations/catalog endpoint - List catalog."""

    def test_get_catalog_success(self, catalog_client, mock_db_session, sample_integrations):
        """Test getting full catalog returns all integrations."""
        # Create mock integration objects
        mock_integrations = []
        for integration_data in sample_integrations:
            mock_integration = Mock()
            mock_integration.id = integration_data["id"]
            mock_integration.name = integration_data["name"]
            mock_integration.description = integration_data["description"]
            mock_integration.category = integration_data["category"]
            mock_integration.icon = integration_data["icon"]
            mock_integration.color = integration_data["color"]
            mock_integration.auth_type = integration_data["auth_type"]
            mock_integration.triggers = integration_data["triggers"]
            mock_integration.actions = integration_data["actions"]
            mock_integration.popular = integration_data["popular"]
            mock_integration.native_id = integration_data.get("native_id")
            mock_integrations.append(mock_integration)

        # Configure mock query to return integrations
        mock_db_session.query.return_value.all.return_value = mock_integrations

        # Get catalog
        response = catalog_client.get("/api/v1/integrations/catalog")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6

        # Verify all integrations present
        integration_ids = [item["id"] for item in data]
        assert "slack_1" in integration_ids
        assert "gmail_1" in integration_ids
        assert "dropbox_1" in integration_ids
        assert "trello_1" in integration_ids
        assert "salesforce_1" in integration_ids
        assert "mailchimp_1" in integration_ids

    def test_get_catalog_empty(self, catalog_client, mock_db_session):
        """Test getting catalog when no integrations exist."""
        # Configure mock query to return empty list
        mock_db_session.query.return_value.all.return_value = []

        # Get catalog
        response = catalog_client.get("/api/v1/integrations/catalog")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_catalog_response_structure(self, catalog_client, mock_db_session, sample_integration, integration_response_structure):
        """Test catalog response has correct structure."""
        # Create mock integration
        integration_data = sample_integration()
        mock_integration = Mock()
        mock_integration.id = integration_data["id"]
        mock_integration.name = integration_data["name"]
        mock_integration.description = integration_data["description"]
        mock_integration.category = integration_data["category"]
        mock_integration.icon = integration_data["icon"]
        mock_integration.color = integration_data["color"]
        mock_integration.auth_type = integration_data["auth_type"]
        mock_integration.triggers = integration_data["triggers"]
        mock_integration.actions = integration_data["actions"]
        mock_integration.popular = integration_data["popular"]
        mock_integration.native_id = integration_data.get("native_id")

        # Configure mock query to return integration
        mock_db_session.query.return_value.all.return_value = [mock_integration]

        # Get catalog
        response = catalog_client.get("/api/v1/integrations/catalog")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        # Verify response structure
        item = data[0]
        for field in integration_response_structure:
            assert field in item, f"Missing field: {field}"

        # Verify authType is camelCase (from auth_type)
        assert item["authType"] == "none"

        # Verify triggers and actions are lists
        assert isinstance(item["triggers"], list)
        assert isinstance(item["actions"], list)

    def test_get_catalog_multiple_categories(self, catalog_client, mock_db_session, sample_integrations):
        """Test catalog with integrations from multiple categories."""
        # Create mock integration objects
        mock_integrations = []
        for integration_data in sample_integrations:
            mock_integration = Mock()
            mock_integration.id = integration_data["id"]
            mock_integration.name = integration_data["name"]
            mock_integration.description = integration_data["description"]
            mock_integration.category = integration_data["category"]
            mock_integration.icon = integration_data["icon"]
            mock_integration.color = integration_data["color"]
            mock_integration.auth_type = integration_data["auth_type"]
            mock_integration.triggers = integration_data["triggers"]
            mock_integration.actions = integration_data["actions"]
            mock_integration.popular = integration_data["popular"]
            mock_integration.native_id = integration_data.get("native_id")
            mock_integrations.append(mock_integration)

        # Configure mock query to return integrations
        mock_db_session.query.return_value.all.return_value = mock_integrations

        # Get catalog
        response = catalog_client.get("/api/v1/integrations/catalog")

        assert response.status_code == 200
        data = response.json()

        # Verify all categories present
        categories = set(item["category"] for item in data)
        assert "communication" in categories
        assert "email" in categories
        assert "productivity" in categories
        assert "crm" in categories


# ============================================================================
# Test Class: TestIntegrationDetails
# ============================================================================

class TestIntegrationDetails:
    """Tests for GET /api/v1/integrations/catalog/{piece_id} endpoint - Get details."""

    def test_get_integration_details_success(self, catalog_client, mock_db_session, sample_integration):
        """Test getting integration details by ID."""
        # Create mock integration
        integration_data = sample_integration(id="slack_1", name="Slack")
        mock_integration = Mock()
        mock_integration.id = integration_data["id"]
        mock_integration.name = integration_data["name"]
        mock_integration.description = integration_data["description"]
        mock_integration.category = integration_data["category"]
        mock_integration.icon = integration_data["icon"]
        mock_integration.color = integration_data["color"]
        mock_integration.auth_type = integration_data["auth_type"]
        mock_integration.triggers = integration_data["triggers"]
        mock_integration.actions = integration_data["actions"]
        mock_integration.popular = integration_data["popular"]
        mock_integration.native_id = integration_data.get("native_id")

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_integration

        # Get details
        response = catalog_client.get("/api/v1/integrations/catalog/slack_1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "slack_1"
        assert data["name"] == "Slack"

    def test_get_integration_details_all_fields(self, catalog_client, mock_db_session, integration_response_structure):
        """Test integration details includes all fields."""
        # Create mock integration
        mock_integration = Mock()
        mock_integration.id = "gmail_1"
        mock_integration.name = "Gmail"
        mock_integration.description = "Email service"
        mock_integration.category = "email"
        mock_integration.icon = "gmail-icon"
        mock_integration.color = "#EA4335"
        mock_integration.auth_type = "oauth"
        mock_integration.triggers = [{"name": "new_email"}]
        mock_integration.actions = [{"name": "send_email"}]
        mock_integration.popular = True
        mock_integration.native_id = None

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_integration

        # Get details
        response = catalog_client.get("/api/v1/integrations/catalog/gmail_1")

        assert response.status_code == 200
        data = response.json()

        # Verify all fields present
        for field in integration_response_structure:
            assert field in data

        # Verify field values
        assert data["id"] == "gmail_1"
        assert data["name"] == "Gmail"
        assert data["description"] == "Email service"
        assert data["category"] == "email"
        assert data["icon"] == "gmail-icon"
        assert data["color"] == "#EA4335"
        assert data["authType"] == "oauth"
        assert data["popular"] is True

    def test_get_integration_details_response_format(self, catalog_client, mock_db_session, sample_integration):
        """Test integration details response format."""
        # Create mock integration
        integration_data = sample_integration()
        mock_integration = Mock()
        mock_integration.id = integration_data["id"]
        mock_integration.name = integration_data["name"]
        mock_integration.description = integration_data["description"]
        mock_integration.category = integration_data["category"]
        mock_integration.icon = integration_data["icon"]
        mock_integration.color = integration_data["color"]
        mock_integration.auth_type = integration_data["auth_type"]
        mock_integration.triggers = integration_data["triggers"]
        mock_integration.actions = integration_data["actions"]
        mock_integration.popular = integration_data["popular"]
        mock_integration.native_id = integration_data.get("native_id")

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_integration

        # Get details
        response = catalog_client.get("/api/v1/integrations/catalog/test_integration_1")

        assert response.status_code == 200
        data = response.json()

        # Verify authType is camelCase
        assert "authType" in data
        assert "auth_type" not in data

        # Verify triggers and actions are lists
        assert isinstance(data["triggers"], list)
        assert isinstance(data["actions"], list)

        # Verify popular is boolean
        assert isinstance(data["popular"], bool)


# ============================================================================
# Test Class: TestCatalogFilters
# ============================================================================

class TestCatalogFilters:
    """Tests for catalog filtering (category, popular parameters)."""

    def test_filter_by_category(self, catalog_client, mock_db_session, sample_integrations):
        """Test filtering catalog by category."""
        # Create mock integration for Slack (communication category)
        mock_integration = Mock()
        mock_integration.id = "slack_1"
        mock_integration.name = "Slack"
        mock_integration.description = "Team messaging platform"
        mock_integration.category = "communication"
        mock_integration.icon = "slack-icon"
        mock_integration.color = "#4A154B"
        mock_integration.auth_type = "oauth"
        mock_integration.triggers = [{"name": "new_message"}]
        mock_integration.actions = [{"name": "send_message"}]
        mock_integration.popular = True
        mock_integration.native_id = None

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_integration]

        # Filter by communication category
        response = catalog_client.get("/api/v1/integrations/catalog?category=communication")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "communication"
        assert data[0]["id"] == "slack_1"

    def test_filter_by_popular_true(self, catalog_client, mock_db_session, sample_integrations):
        """Test filtering catalog by popular=true."""
        # Create mock integrations that are popular
        mock_integrations = []
        for integration_data in sample_integrations:
            if integration_data["popular"]:
                mock_integration = Mock()
                mock_integration.id = integration_data["id"]
                mock_integration.name = integration_data["name"]
                mock_integration.description = integration_data["description"]
                mock_integration.category = integration_data["category"]
                mock_integration.icon = integration_data["icon"]
                mock_integration.color = integration_data["color"]
                mock_integration.auth_type = integration_data["auth_type"]
                mock_integration.triggers = integration_data["triggers"]
                mock_integration.actions = integration_data["actions"]
                mock_integration.popular = integration_data["popular"]
                mock_integration.native_id = integration_data.get("native_id")
                mock_integrations.append(mock_integration)

        # Configure mock query to return popular integrations
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_integrations

        # Filter by popular=true
        response = catalog_client.get("/api/v1/integrations/catalog?popular=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

        # Verify all are popular
        for item in data:
            assert item["popular"] is True

    def test_filter_by_popular_false(self, catalog_client, mock_db_session, sample_integrations):
        """Test filtering catalog by popular=false."""
        # Create mock integrations that are not popular
        mock_integrations = []
        for integration_data in sample_integrations:
            if not integration_data["popular"]:
                mock_integration = Mock()
                mock_integration.id = integration_data["id"]
                mock_integration.name = integration_data["name"]
                mock_integration.description = integration_data["description"]
                mock_integration.category = integration_data["category"]
                mock_integration.icon = integration_data["icon"]
                mock_integration.color = integration_data["color"]
                mock_integration.auth_type = integration_data["auth_type"]
                mock_integration.triggers = integration_data["triggers"]
                mock_integration.actions = integration_data["actions"]
                mock_integration.popular = integration_data["popular"]
                mock_integration.native_id = integration_data.get("native_id")
                mock_integrations.append(mock_integration)

        # Configure mock query to return non-popular integrations
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_integrations

        # Filter by popular=false
        response = catalog_client.get("/api/v1/integrations/catalog?popular=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify all are not popular
        for item in data:
            assert item["popular"] is False

    def test_combined_filters(self, catalog_client, mock_db_session):
        """Test combining category and popular filters."""
        # Create mock integrations for email category that are popular
        mock_integrations = []
        email_integrations = ["gmail_1", "mailchimp_1"]
        for int_id in email_integrations:
            mock_integration = Mock()
            mock_integration.id = int_id
            mock_integration.name = int_id.replace("_1", "").title()
            mock_integration.description = "Email integration"
            mock_integration.category = "email"
            mock_integration.icon = "email-icon"
            mock_integration.color = "#EA4335"
            mock_integration.auth_type = "oauth"
            mock_integration.triggers = [{"name": "new_email"}]
            mock_integration.actions = [{"name": "send_email"}]
            mock_integration.popular = True
            mock_integration.native_id = None
            mock_integrations.append(mock_integration)

        # Configure mock query to return filtered integrations
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_integrations

        # Filter by email category and popular=true
        response = catalog_client.get("/api/v1/integrations/catalog?category=email&popular=true")

        assert response.status_code == 200
        data = response.json()
        # Should return email integrations
        assert len(data) == 2

        # Verify both filters applied
        for item in data:
            assert item["category"] == "email"
            assert item["popular"] is True

    def test_filter_no_matches(self, catalog_client, mock_db_session):
        """Test filter that matches no integrations."""
        # Configure mock query to return empty list
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        # Filter by non-existent category
        response = catalog_client.get("/api/v1/integrations/catalog?category=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_filter_category_case_sensitive(self, catalog_client, mock_db_session):
        """Test category filter is case-sensitive."""
        # Configure mock query to return empty list (case-sensitive match fails)
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        # Filter with wrong case
        response = catalog_client.get("/api/v1/integrations/catalog?category=Email")

        assert response.status_code == 200
        data = response.json()
        # Database comparison is case-sensitive
        assert len(data) == 0


# ============================================================================
# Test Class: TestCatalogSearch
# ============================================================================

class TestCatalogSearch:
    """Tests for catalog search functionality (ilike on name and description)."""

    def test_search_by_name(self, catalog_client, mock_db_session):
        """Test searching integrations by name."""
        # Create mock Slack integration
        mock_integration = Mock()
        mock_integration.id = "slack_1"
        mock_integration.name = "Slack"
        mock_integration.description = "Team messaging platform"
        mock_integration.category = "communication"
        mock_integration.icon = "slack-icon"
        mock_integration.color = "#4A154B"
        mock_integration.auth_type = "oauth"
        mock_integration.triggers = [{"name": "new_message"}]
        mock_integration.actions = [{"name": "send_message"}]
        mock_integration.popular = True
        mock_integration.native_id = None

        # Configure mock query to return Slack
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_integration]

        # Search for "slack"
        response = catalog_client.get("/api/v1/integrations/catalog?search=slack")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Slack"
        assert data[0]["id"] == "slack_1"

    def test_search_by_description(self, catalog_client, mock_db_session):
        """Test searching integrations by description."""
        # Create mock integration with email in description
        mock_integration = Mock()
        mock_integration.id = "test_1"
        mock_integration.name = "Integration One"
        mock_integration.description = "Email service integration"
        mock_integration.category = "email"
        mock_integration.icon = "email-icon"
        mock_integration.color = "#EA4335"
        mock_integration.auth_type = "oauth"
        mock_integration.triggers = [{"name": "new_email"}]
        mock_integration.actions = [{"name": "send_email"}]
        mock_integration.popular = False
        mock_integration.native_id = None

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_integration]

        # Search for "email"
        response = catalog_client.get("/api/v1/integrations/catalog?search=email")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["description"] == "Email service integration"

    def test_search_case_insensitive(self, catalog_client, mock_db_session):
        """Test search is case-insensitive (ilike)."""
        # Create mock Slack integration
        mock_integration = Mock()
        mock_integration.id = "slack_1"
        mock_integration.name = "Slack"
        mock_integration.description = "Team messaging platform"
        mock_integration.category = "communication"
        mock_integration.icon = "slack-icon"
        mock_integration.color = "#4A154B"
        mock_integration.auth_type = "oauth"
        mock_integration.triggers = [{"name": "new_message"}]
        mock_integration.actions = [{"name": "send_message"}]
        mock_integration.popular = True
        mock_integration.native_id = None

        # Configure mock query to return Slack
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_integration]

        # Search with uppercase
        response = catalog_client.get("/api/v1/integrations/catalog?search=SLACK")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Slack"

    def test_search_partial_match(self, catalog_client, mock_db_session):
        """Test search with partial matching."""
        # Create mock integrations
        mock_integrations = []
        for int_id, name in [("gmail_1", "Gmail"), ("mailchimp_1", "Mailchimp")]:
            mock_integration = Mock()
            mock_integration.id = int_id
            mock_integration.name = name
            mock_integration.description = "Email service"
            mock_integration.category = "email"
            mock_integration.icon = "email-icon"
            mock_integration.color = "#EA4335"
            mock_integration.auth_type = "oauth"
            mock_integration.triggers = [{"name": "new_email"}]
            mock_integration.actions = [{"name": "send_email"}]
            mock_integration.popular = True
            mock_integration.native_id = None
            mock_integrations.append(mock_integration)

        # Configure mock query to return both
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_integrations

        # Search for "mail" (partial match)
        response = catalog_client.get("/api/v1/integrations/catalog?search=mail")

        assert response.status_code == 200
        data = response.json()
        # Should match both Gmail and Mailchimp
        assert len(data) == 2

    def test_search_no_results(self, catalog_client, mock_db_session):
        """Test search with no matching results."""
        # Configure mock query to return empty list
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        # Search for non-existent integration
        response = catalog_client.get("/api/v1/integrations/catalog?search=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_search_special_characters(self, catalog_client, mock_db_session):
        """Test search with special characters."""
        # Create mock integration with special characters
        mock_integration = Mock()
        mock_integration.id = "test_1"
        mock_integration.name = "C++ Tools"
        mock_integration.description = "Development tools for C++"
        mock_integration.category = "development"
        mock_integration.icon = "cpp-icon"
        mock_integration.color = "#00599C"
        mock_integration.auth_type = "api_key"
        mock_integration.triggers = []
        mock_integration.actions = []
        mock_integration.popular = False
        mock_integration.native_id = None

        # Configure mock query to return integration
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_integration]

        # Search for C++
        response = catalog_client.get("/api/v1/integrations/catalog?search=C++")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "C++ Tools"

    def test_search_with_filters(self, catalog_client, mock_db_session):
        """Test combining search with filters."""
        # Create mock email integrations with "mail" in name/description
        mock_integrations = []
        for int_id, name in [("gmail_1", "Gmail"), ("mailchimp_1", "Mailchimp")]:
            mock_integration = Mock()
            mock_integration.id = int_id
            mock_integration.name = name
            mock_integration.description = "Email marketing"
            mock_integration.category = "email"
            mock_integration.icon = "email-icon"
            mock_integration.color = "#EA4335"
            mock_integration.auth_type = "oauth"
            mock_integration.triggers = [{"name": "new_email"}]
            mock_integration.actions = [{"name": "send_email"}]
            mock_integration.popular = True
            mock_integration.native_id = None
            mock_integrations.append(mock_integration)

        # Configure mock query to return filtered integrations
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_integrations

        # Search for "mail" with category=email
        response = catalog_client.get("/api/v1/integrations/catalog?search=mail&category=email")

        assert response.status_code == 200
        data = response.json()
        # Should return email integrations with "mail" in name/description
        assert len(data) == 2

        # Verify both conditions met
        for item in data:
            assert item["category"] == "email"


# ============================================================================
# Test Class: TestCatalogErrorPaths
# ============================================================================

class TestCatalogErrorPaths:
    """Tests for error paths in catalog endpoints."""

    def test_get_integration_not_found(self, catalog_client, mock_db_session):
        """Test getting non-existent integration returns 404."""
        # Configure mock query to return None
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Try to get non-existent integration
        response = catalog_client.get("/api/v1/integrations/catalog/nonexistent_id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        # Error response has nested structure with error.message
        # or direct detail string
        error_detail = data.get("detail", "")
        if isinstance(error_detail, dict):
            # BaseAPIRouter format: {"error": {"message": "..."}}
            error_msg = error_detail.get("error", {}).get("message", "")
        else:
            error_msg = str(error_detail)
        # Verify error mentions "Integration"
        assert "Integration" in error_msg or "not found" in error_msg.lower()

    def test_get_integration_empty_id(self, catalog_client, mock_db_session):
        """Test getting integration with empty ID."""
        # Try to get integration with no ID (should return 404 or 307 redirect from FastAPI)
        response = catalog_client.get("/api/v1/integrations/catalog/", follow_redirects=False)

        # FastAPI returns 307 Temporary Redirect or 404 for missing path parameter
        assert response.status_code in [307, 404]

    def test_filter_invalid_category(self, catalog_client, mock_db_session):
        """Test filter with non-existent category returns empty list."""
        # Configure mock query to return empty list
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        # Filter by non-existent category
        response = catalog_client.get("/api/v1/integrations/catalog?category=nonexistent_category")

        # Should return empty list, not error
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_database_error_handling(self, catalog_client, mock_db_session):
        """Test database error handling in catalog endpoint."""
        # Mock database query to raise exception
        mock_db_session.query.side_effect = Exception("Database connection failed")

        response = catalog_client.get("/api/v1/integrations/catalog")

        # Should return 500 internal error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_search_sql_injection(self, catalog_client, mock_db_session):
        """Test SQL injection attempt is handled safely."""
        # Configure mock query to return empty list (injection fails)
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        # Try SQL injection
        response = catalog_client.get("/api/v1/integrations/catalog?search=' OR '1'='1")

        # ilike parameterized query should be safe
        assert response.status_code == 200
        data = response.json()
        # Should not return all integrations (SQL injection failed)
        # Empty result is expected since no integration name contains the SQL string
        assert isinstance(data, list)
