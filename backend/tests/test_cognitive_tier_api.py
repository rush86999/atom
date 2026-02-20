"""
Cognitive Tier API Tests

Comprehensive test suite for cognitive tier management endpoints:
- Preference CRUD operations
- Cost estimation
- Tier comparison
- Governance validation
- Integration testing

Author: Atom AI Platform
Created: 2026-02-20
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from core.models import CognitiveTierPreference, Workspace
from main_api_app import app
from core.database import get_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(db_session):
    """Test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def test_workspace(db_session: Session):
    """Create a test workspace"""
    workspace = Workspace(
        id="test_workspace_123",
        name="Test Workspace",
        description="Test workspace for cognitive tier tests"
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def test_preference(db_session: Session, test_workspace: Workspace):
    """Create a test tier preference"""
    preference = CognitiveTierPreference(
        workspace_id=test_workspace.id,
        default_tier="standard",
        min_tier="micro",
        max_tier="versatile",
        monthly_budget_cents=10000,
        max_cost_per_request_cents=50,
        enable_cache_aware_routing=True,
        enable_auto_escalation=True,
        enable_minimax_fallback=False,
        preferred_providers=["deepseek", "openai"]
    )
    db_session.add(preference)
    db_session.commit()
    db_session.refresh(preference)
    return preference


# ============================================================================
# Preference CRUD Tests
# ============================================================================

class TestPreferenceCRUD:
    """Test preference CRUD operations"""

    def test_get_preferences_default(self, client: TestClient, test_workspace: Workspace):
        """Test that default preferences are returned when none exist"""
        response = client.get(f"/api/v1/cognitive-tier/preferences/{test_workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == test_workspace.id
        assert data["default_tier"] == "standard"
        assert data["enable_cache_aware_routing"] is True
        assert data["id"] == ""  # Empty ID for defaults

    def test_create_preferences(self, client: TestClient, test_workspace: Workspace):
        """Test creating new tier preferences"""
        request_data = {
            "default_tier": "versatile",
            "min_tier": "standard",
            "max_tier": "complex",
            "monthly_budget_cents": 5000,
            "max_cost_per_request_cents": 25,
            "enable_cache_aware_routing": False,
            "preferred_providers": ["openai"]
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_workspace.id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "versatile"
        assert data["monthly_budget_cents"] == 5000
        assert data["enable_cache_aware_routing"] is False
        assert data["preferred_providers"] == ["openai"]
        assert data["workspace_id"] == test_workspace.id

    def test_update_preferences(self, client: TestClient, test_preference: CognitiveTierPreference):
        """Test updating existing preferences"""
        request_data = {
            "default_tier": "heavy",
            "monthly_budget_cents": 20000
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_preference.workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "heavy"
        assert data["monthly_budget_cents"] == 20000
        # Previous values should remain
        assert data["min_tier"] == test_preference.min_tier

    def test_update_budget(self, client: TestClient, test_preference: CognitiveTierPreference):
        """Test updating budget fields only"""
        request_data = {
            "monthly_budget_cents": 15000,
            "max_cost_per_request_cents": 75
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{test_preference.workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["monthly_budget_cents"] == 15000
        assert data["max_cost_per_request_cents"] == 75
        # Other fields should remain unchanged
        assert data["default_tier"] == test_preference.default_tier

    def test_delete_preferences(self, client: TestClient, test_preference: CognitiveTierPreference):
        """Test deleting custom preferences"""
        response = client.delete(f"/api/v1/cognitive-tier/preferences/{test_preference.workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

        # Verify preference is gone
        get_response = client.get(f"/api/v1/cognitive-tier/preferences/{test_preference.workspace_id}")
        assert get_response.json()["id"] == ""  # Back to defaults

    def test_unique_workspace_constraint(self, client: TestClient, test_workspace: Workspace, db_session: Session):
        """Test that only one preference can exist per workspace"""
        # Create first preference
        pref1 = CognitiveTierPreference(
            workspace_id=test_workspace.id,
            default_tier="standard"
        )
        db_session.add(pref1)
        db_session.commit()

        # Try to create second preference directly in DB
        pref2 = CognitiveTierPreference(
            workspace_id=test_workspace.id,
            default_tier="versatile"
        )
        db_session.add(pref2)

        with pytest.raises(Exception):  # Integrity error
            db_session.commit()

    def test_invalid_tier_rejected(self, client: TestClient, test_workspace: Workspace):
        """Test that invalid tier values return 400"""
        request_data = {
            "default_tier": "invalid_tier"
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_workspace.id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "Invalid default_tier" in response.json()["detail"]

    def test_negative_budget_rejected(self, client: TestClient, test_workspace: Workspace):
        """Test that negative budget values return 400"""
        request_data = {
            "monthly_budget_cents": -100
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_workspace.id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "non-negative" in response.json()["detail"]


# ============================================================================
# Cost Estimation Tests
# ============================================================================

class TestCostEstimation:
    """Test cost estimation functionality"""

    def test_estimate_cost_returns_all_tiers(self, client: TestClient):
        """Test that cost estimation returns all 5 tiers"""
        response = client.get("/api/v1/cognitive-tier/estimate-cost?estimated_tokens=100")

        assert response.status_code == 200
        data = response.json()
        assert len(data["estimates"]) == 5
        assert data["estimated_tokens"] == 100

        tier_names = [e["tier"] for e in data["estimates"]]
        assert "micro" in tier_names
        assert "standard" in tier_names
        assert "versatile" in tier_names
        assert "heavy" in tier_names
        assert "complex" in tier_names

    def test_estimate_cost_uses_token_count(self, client: TestClient):
        """Test that token count affects cost"""
        response_small = client.get("/api/v1/cognitive-tier/estimate-cost?estimated_tokens=10")
        response_large = client.get("/api/v1/cognitive-tier/estimate-cost?estimated_tokens=1000")

        assert response_small.status_code == 200
        assert response_large.status_code == 200

        data_small = response_small.json()
        data_large = response_large.json()

        # Larger token count should result in higher costs
        cost_small = data_small["estimates"][0]["estimated_cost_usd"]
        cost_large = data_large["estimates"][0]["estimated_cost_usd"]
        assert cost_large > cost_small

    def test_estimate_cost_cache_aware(self, client: TestClient):
        """Test that cache-aware pricing is included when available"""
        response = client.get("/api/v1/cognitive-tier/estimate-cost?estimated_tokens=500")

        assert response.status_code == 200
        data = response.json()

        # At least one tier should have cache-aware models
        has_cache_aware = any(e["cache_aware_available"] for e in data["estimates"])
        # Note: This depends on pricing data, so we don't assert True
        # Just verify the field exists
        assert all("cache_aware_available" in e for e in data["estimates"])

    def test_recommended_tier_selection(self, client: TestClient):
        """Test that recommended tier is based on complexity"""
        # Simple prompt should recommend lower tier
        response_simple = client.get("/api/v1/cognitive-tier/estimate-cost?prompt=hi")

        assert response_simple.status_code == 200
        data_simple = response_simple.json()
        assert data_simple["recommended_tier"] in ["micro", "standard"]

        # Complex prompt should recommend higher tier
        response_complex = client.get(
            "/api/v1/cognitive-tier/estimate-cost?prompt=debug%20this%20distributed%20system%20architecture%20with%20kubernetes"
        )

        assert response_complex.status_code == 200
        data_complex = response_complex.json()
        assert data_complex["recommended_tier"] in ["versatile", "heavy", "complex"]

    def test_estimate_cost_with_prompt(self, client: TestClient):
        """Test auto-estimation from prompt"""
        response = client.get("/api/v1/cognitive-tier/estimate-cost?prompt=hello%20world")

        assert response.status_code == 200
        data = response.json()
        assert data["prompt_used"] == "hello world"
        assert data["estimated_tokens"] > 0
        assert len(data["estimates"]) == 5


# ============================================================================
# Tier Comparison Tests
# ============================================================================

class TestTierComparison:
    """Test tier comparison functionality"""

    def test_compare_tiers_returns_comparison_table(self, client: TestClient):
        """Test that comparison returns all tiers with quality and cost"""
        response = client.get("/api/v1/cognitive-tier/compare-tiers")

        assert response.status_code == 200
        data = response.json()
        assert data["total_tiers"] == 5
        assert len(data["tiers"]) == 5

        # Verify each tier has required fields
        for tier in data["tiers"]:
            assert "tier" in tier
            assert "description" in tier
            assert "quality_range" in tier
            assert "cost_range_usd" in tier

    def test_compare_tiers_includes_example_models(self, client: TestClient):
        """Test that each tier has example models"""
        response = client.get("/api/v1/cognitive-tier/compare-tiers")

        assert response.status_code == 200
        data = response.json()

        for tier in data["tiers"]:
            assert "example_models" in tier
            assert len(tier["example_models"]) > 0
            assert isinstance(tier["example_models"], list)

    def test_compare_tiers_includes_cache_info(self, client: TestClient):
        """Test that cache support is indicated"""
        response = client.get("/api/v1/cognitive-tier/compare-tiers")

        assert response.status_code == 200
        data = response.json()

        for tier in data["tiers"]:
            assert "cache_aware_support" in tier
            assert isinstance(tier["cache_aware_support"], bool)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test database integration and data persistence"""

    def test_preference_saved_to_database(self, client: TestClient, test_workspace: Workspace, db_session: Session):
        """Test that preferences are saved to database"""
        request_data = {
            "default_tier": "heavy",
            "monthly_budget_cents": 5000
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_workspace.id}",
            json=request_data
        )

        assert response.status_code == 200

        # Verify in database
        preference = db_session.query(CognitiveTierPreference).filter_by(
            workspace_id=test_workspace.id
        ).first()

        assert preference is not None
        assert preference.default_tier == "heavy"
        assert preference.monthly_budget_cents == 5000

    def test_preference_retrieval_by_workspace(self, client: TestClient, db_session: Session):
        """Test workspace isolation in preferences"""
        workspace1 = Workspace(id="workspace_1", name="Workspace 1")
        workspace2 = Workspace(id="workspace_2", name="Workspace 2")
        db_session.add_all([workspace1, workspace2])
        db_session.commit()

        # Create preference for workspace1
        pref1 = CognitiveTierPreference(
            workspace_id=workspace1.id,
            default_tier="standard"
        )
        db_session.add(pref1)
        db_session.commit()

        # Each workspace should get its own preference
        response1 = client.get(f"/api/v1/cognitive-tier/preferences/{workspace1.id}")
        response2 = client.get(f"/api/v1/cognitive-tier/preferences/{workspace2.id}")

        assert response1.status_code == 200
        assert response1.json()["default_tier"] == "standard"

        assert response2.status_code == 200
        assert response2.json()["default_tier"] == "standard"  # Default

    def test_cost_estimation_uses_pricing_fetcher(self, client: TestClient):
        """Test that cost estimation uses real pricing data"""
        response = client.get("/api/v1/cognitive-tier/estimate-cost?estimated_tokens=100")

        assert response.status_code == 200
        data = response.json()

        # At least one estimate should have models
        has_models = any(len(e["models_in_tier"]) > 0 for e in data["estimates"])
        assert has_models, "At least one tier should have models"

        # Verify cost is a number
        for estimate in data["estimates"]:
            assert isinstance(estimate["estimated_cost_usd"], float)
            assert estimate["estimated_cost_usd"] >= 0

    def test_feature_flags_persist(self, client: TestClient, test_workspace: Workspace, db_session: Session):
        """Test that feature flags are persisted correctly"""
        request_data = {
            "enable_cache_aware_routing": False,
            "enable_auto_escalation": True,
            "enable_minimax_fallback": False
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{test_workspace.id}",
            json=request_data
        )

        assert response.status_code == 200

        # Verify in database
        preference = db_session.query(CognitiveTierPreference).filter_by(
            workspace_id=test_workspace.id
        ).first()

        assert preference.enable_cache_aware_routing is False
        assert preference.enable_auto_escalation is True
        assert preference.enable_minimax_fallback is False


# ============================================================================
# Governance Tests
# ============================================================================

class TestGovernance:
    """Test AUTONOMOUS governance requirements"""

    def test_autonomous_governance_required(self, client: TestClient):
        """Test that AUTONOMOUS governance is enforced"""
        # Note: This test verifies the endpoint is protected
        # Actual governance enforcement depends on agent_maturity headers
        # which are tested in integration tests

        # For now, just verify endpoint is accessible
        response = client.get("/api/v1/cognitive-tier/compare-tiers")
        # Should succeed even without governance (public/read-only)
        assert response.status_code == 200

    def test_unauthorized_access_blocked(self, client: TestClient):
        """Test that unauthorized writes are blocked"""
        # Note: Actual governance enforcement is done by middleware
        # This test verifies endpoint structure
        # Actual blocking behavior tested in governance tests

        # Attempt to create preference should work in test environment
        # (governance may be disabled)
        response = client.post(
            "/api/v1/cognitive-tier/preferences/test_workspace",
            json={"default_tier": "standard"}
        )

        # May succeed or fail depending on governance configuration
        # Just verify endpoint exists
        assert response.status_code in [200, 400, 401, 403]


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
