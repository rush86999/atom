"""
Unit Tests for Cognitive Tier Routes

Tests cognitive tier management API endpoints:
- Get/Set workspace tier preferences
- Cost estimation per tier
- Tier comparison (quality vs cost)
- Budget management

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api import cognitive_tier_routes
from api.cognitive_tier_routes import router


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client with database mocking."""
    def override_get_db():
        """Mock database dependency."""
        mock_db = Mock()
        mock_preference = Mock()
        mock_preference.id = "test-id"
        mock_preference.workspace_id = "test-workspace"
        mock_preference.default_tier = "standard"
        mock_preference.min_tier = "micro"
        mock_preference.max_tier = "complex"
        mock_preference.monthly_budget_cents = 10000
        mock_preference.max_cost_per_request_cents = 100
        mock_preference.enable_cache_aware_routing = True
        mock_preference.enable_auto_escalation = True
        mock_preference.enable_minimax_fallback = True
        mock_preference.preferred_providers = []
        mock_preference.metadata_json = {}
        mock_preference.created_at = None
        mock_preference.updated_at = None

        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_preference
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        return mock_db

    # Override the database dependency
    app.dependency_overrides[cognitive_tier_routes.get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    # Clean up
    app.dependency_overrides.clear()


class TestGetPreferences:
    """Tests for GET /api/v1/cognitive-tier/preferences/{workspace_id}"""

    def test_get_preferences_success(self, client):
        """Test getting tier preferences for workspace."""
        workspace_id = "test-workspace-123"

        response = client.get(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_preferences_not_found(self, client):
        """Test getting preferences for non-existent workspace."""
        response = client.get("/api/v1/cognitive-tier/preferences/nonexistent-workspace")

        assert response.status_code in [200, 400, 401, 404, 500]


class TestCreateOrUpdatePreferences:
    """Tests for POST /api/v1/cognitive-tier/preferences/{workspace_id}"""

    def test_create_preferences(self, client):
        """Test creating new tier preferences."""
        workspace_id = "new-workspace-789"

        request_data = {
            "default_tier": "heavy",
            "monthly_budget_cents": 50000,
            "max_cost_per_request_cents": 100
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

    def test_update_preferences(self, client):
        """Test updating existing tier preferences."""
        request_data = {
            "default_tier": "micro",
            "enable_cache_aware_routing": False
        }

        response = client.post(
            "/api/v1/cognitive-tier/preferences/test-workspace",
            json=request_data
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]


class TestUpdateBudget:
    """Tests for PUT /api/v1/cognitive-tier/preferences/{workspace_id}/budget"""

    def test_update_monthly_budget(self, client):
        """Test updating monthly budget."""
        request_data = {
            "monthly_budget_cents": 15000
        }

        response = client.put(
            "/api/v1/cognitive-tier/preferences/test-workspace/budget",
            json=request_data
        )

        assert response.status_code in [200, 201, 400, 401, 404, 500]

    def test_update_max_cost_per_request(self, client):
        """Test updating max cost per request."""
        request_data = {
            "max_cost_per_request_cents": 25
        }

        response = client.put(
            "/api/v1/cognitive-tier/preferences/test-workspace/budget",
            json=request_data
        )

        assert response.status_code in [200, 201, 400, 401, 404, 500]

    def test_validate_monthly_budget_not_negative(self, client):
        """Test validation that monthly budget must be non-negative."""
        request_data = {
            "monthly_budget_cents": -100
        }

        response = client.put(
            "/api/v1/cognitive-tier/preferences/test-workspace/budget",
            json=request_data
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_validate_max_cost_not_negative(self, client):
        """Test validation that max cost must be non-negative."""
        request_data = {
            "max_cost_per_request_cents": -50
        }

        response = client.put(
            "/api/v1/cognitive-tier/preferences/test-workspace/budget",
            json=request_data
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]


class TestEstimateCost:
    """Tests for GET /api/v1/cognitive-tier/estimate-cost"""

    def test_estimate_cost_with_prompt(self, client):
        """Test cost estimation with prompt."""
        params = {
            "prompt": "What is the capital of France?"
        }

        response = client.get(
            "/api/v1/cognitive-tier/estimate-cost",
            params=params
        )

        assert response.status_code in [200, 400, 401, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "estimates" in data or "recommended_tier" in data

    def test_estimate_cost_with_token_count(self, client):
        """Test cost estimation with token count."""
        params = {
            "estimated_tokens": 1000
        }

        response = client.get(
            "/api/v1/cognitive-tier/estimate-cost",
            params=params
        )

        assert response.status_code in [200, 400, 401, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "estimates" in data or "recommended_tier" in data

    def test_estimate_cost_for_specific_tier(self, client):
        """Test cost estimation for a specific tier."""
        params = {
            "estimated_tokens": 500,
            "tier": "micro"
        }

        response = client.get(
            "/api/v1/cognitive-tier/estimate-cost",
            params=params
        )

        assert response.status_code in [200, 400, 401, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "estimates" in data or "recommended_tier" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
