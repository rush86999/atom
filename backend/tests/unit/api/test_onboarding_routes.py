"""
Unit Tests for Onboarding Routes

Tests user onboarding endpoints:
- POST /api/onboarding/update - Update onboarding status
- GET /api/onboarding/status - Get onboarding status
- Error cases: validation errors, missing fields, authentication

Target Coverage: 85%
Target Branch Coverage: 60%+
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from api import onboarding_routes
from core.models import User
from tests.factories.user_factory import UserFactory


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def mock_user():
    """Mock current user."""
    user = MagicMock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.onboarding_step = "welcome"
    user.onboarding_completed = False
    return user


@pytest.fixture
def client(mock_db, mock_user):
    """Test client with mocked dependencies using FastAPI dependency overrides."""
    from fastapi import FastAPI

    # Create a minimal FastAPI app with the router
    app = FastAPI()
    app.include_router(onboarding_routes.router)

    # Use FastAPI's dependency override mechanism
    app.dependency_overrides[onboarding_routes.get_db] = lambda: mock_db
    app.dependency_overrides[onboarding_routes.get_current_user] = lambda: mock_user

    yield TestClient(app)

    # Clean up overrides
    app.dependency_overrides = {}


# =============================================================================
# Test Update Onboarding Status
# =============================================================================

class TestUpdateOnboardingStatus:
    """Tests for POST /api/onboarding/update endpoint."""

    def test_update_onboarding_step(self, client, mock_db, mock_user):
        """Test updating onboarding step."""
        # Arrange: Prepare update data
        update_data = {
            "step": "profile_setup",
            "completed": None
        }

        # Act: Update onboarding step
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify step updated
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == "profile_setup"
        assert data["data"]["onboarding_completed"] is False
        assert "updated successfully" in data["message"].lower()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user)

    def test_update_onboarding_completed(self, client, mock_db, mock_user):
        """Test marking onboarding as completed."""
        # Arrange: Prepare completion data
        update_data = {
            "step": None,
            "completed": True
        }

        # Act: Mark onboarding as completed
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify completion status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == "welcome"
        assert data["data"]["onboarding_completed"] is True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user)

    def test_update_both_step_and_completed(self, client, mock_db, mock_user):
        """Test updating both step and completion status."""
        # Arrange: Prepare update data with both fields
        update_data = {
            "step": "review_complete",
            "completed": True
        }

        # Act: Update both fields
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify both fields updated
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == "review_complete"
        assert data["data"]["onboarding_completed"] is True
        mock_db.commit.assert_called_once()

    def test_update_onboarding_with_null_values(self, client, mock_db, mock_user):
        """Test updating with null values (no-op)."""
        # Arrange: Prepare update data with null values
        update_data = {
            "step": None,
            "completed": None
        }

        # Act: Send update with nulls
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify request succeeds (no-op)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == "welcome"
        assert data["data"]["onboarding_completed"] is False
        mock_db.commit.assert_called_once()

    def test_update_onboarding_empty_step(self, client, mock_db, mock_user):
        """Test updating onboarding with empty string step."""
        # Arrange: Prepare update data with empty step
        update_data = {
            "step": "",
            "completed": None
        }

        # Act: Update with empty step
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify empty string accepted
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == ""

    def test_update_onboarding_various_steps(self, client, mock_db, mock_user):
        """Test updating through various onboarding steps."""
        # Test different onboarding steps
        steps = ["profile_setup", "workspace_setup", "team_setup", "integration_setup", "review_complete"]

        for step in steps:
            update_data = {"step": step, "completed": False}
            response = client.post("/api/onboarding/update", json=update_data)

            assert response.status_code == 200, f"Failed for step: {step}"
            data = response.json()
            assert data["data"]["onboarding_step"] == step

    def test_update_onboarding_with_extra_fields(self, client, mock_db, mock_user):
        """Test updating onboarding with extra unknown fields."""
        # Arrange: Extra fields not in schema (Pydantic will ignore them)
        update_data = {
            "step": "profile_setup",
            "completed": False,
            "extra_field": "should_be_ignored",
            "another_extra": 123
        }

        # Act: Update with extra fields
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Request succeeds (Pydantic ignores extra fields by default)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == "profile_setup"

    def test_update_onboarding_invalid_json(self, client, mock_db, mock_user):
        """Test updating with invalid JSON."""
        # Act: Send invalid JSON
        response = client.post(
            "/api/onboarding/update",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        # Assert: Verify validation error
        assert response.status_code == 422


# =============================================================================
# Test Get Onboarding Status
# =============================================================================

class TestGetOnboardingStatus:
    """Tests for GET /api/onboarding/status endpoint."""

    def test_get_onboarding_status_initial(self, client, mock_user):
        """Test getting initial onboarding status."""
        # Arrange: User at initial state
        mock_user.onboarding_step = "welcome"
        mock_user.onboarding_completed = False

        # Act: Get onboarding status
        response = client.get("/api/onboarding/status")

        # Assert: Verify initial status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["onboarding_step"] == "welcome"
        assert data["data"]["onboarding_completed"] is False

    def test_get_onboarding_status_in_progress(self, client, mock_user):
        """Test getting onboarding status while in progress."""
        # Arrange: User in middle of onboarding
        mock_user.onboarding_step = "workspace_setup"
        mock_user.onboarding_completed = False

        # Act: Get onboarding status
        response = client.get("/api/onboarding/status")

        # Assert: Verify in-progress status
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == "workspace_setup"
        assert data["data"]["onboarding_completed"] is False

    def test_get_onboarding_status_completed(self, client, mock_user):
        """Test getting onboarding status after completion."""
        # Arrange: User completed onboarding
        mock_user.onboarding_step = "review_complete"
        mock_user.onboarding_completed = True

        # Act: Get onboarding status
        response = client.get("/api/onboarding/status")

        # Assert: Verify completed status
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == "review_complete"
        assert data["data"]["onboarding_completed"] is True

    def test_get_onboarding_status_multiple_calls(self, client, mock_user):
        """Test multiple status GET requests."""
        # Act: Get status multiple times
        for i in range(3):
            mock_user.onboarding_step = f"step_{i}"
            response = client.get("/api/onboarding/status")

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["onboarding_step"] == f"step_{i}"

    def test_get_onboarding_status_no_db_call(self, client, mock_db):
        """Test that status GET doesn't make database calls."""
        # Act: Get status (should only use current_user from auth)
        response = client.get("/api/onboarding/status")

        # Assert: No database operations
        assert response.status_code == 200
        mock_db.commit.assert_not_called()
        mock_db.refresh.assert_not_called()


# =============================================================================
# Test Authentication and Authorization
# =============================================================================

class TestOnboardingAuthentication:
    """Tests for onboarding authentication requirements."""

    def test_update_status_requires_authentication(self, mock_db, mock_user):
        """Test that updating status requires authenticated user."""
        from fastapi import FastAPI
        from api import onboarding_routes

        # Create app without auth override
        app = FastAPI()
        app.include_router(onboarding_routes.router)
        app.dependency_overrides[onboarding_routes.get_db] = lambda: mock_db
        # Don't override get_current_user - should fail

        client = TestClient(app)
        update_data = {"step": "profile_setup"}

        # Act: Try to update without auth
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Unauthorized
        assert response.status_code == 401 or response.status_code == 403

    def test_get_status_requires_authentication(self, mock_db):
        """Test that getting status requires authenticated user."""
        from fastapi import FastAPI
        from api import onboarding_routes

        # Create app without auth override
        app = FastAPI()
        app.include_router(onboarding_routes.router)
        app.dependency_overrides[onboarding_routes.get_db] = lambda: mock_db
        # Don't override get_current_user - should fail

        client = TestClient(app)

        # Act: Try to get status without auth
        response = client.get("/api/onboarding/status")

        # Assert: Unauthorized
        assert response.status_code == 401 or response.status_code == 403


# =============================================================================
# Test Edge Cases and Error Handling
# =============================================================================

class TestOnboardingEdgeCases:
    """Tests for edge cases and error handling."""

    def test_update_with_special_characters_in_step(self, client, mock_db, mock_user):
        """Test updating step with special characters."""
        # Arrange: Step with special characters
        update_data = {
            "step": "step_with-special_ch@racters!",
            "completed": False
        }

        # Act: Update with special chars
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Accepted (API doesn't validate step names)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == "step_with-special_ch@racters!"

    def test_update_with_very_long_step_name(self, client, mock_db, mock_user):
        """Test updating with very long step name."""
        # Arrange: Very long step name
        long_step = "a" * 1000
        update_data = {"step": long_step, "completed": False}

        # Act: Update with long step
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Accepted (no length validation in API)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == long_step

    def test_update_with_unicode_step_name(self, client, mock_db, mock_user):
        """Test updating with Unicode characters in step."""
        # Arrange: Unicode step name
        update_data = {
            "step": "设置_个人资料",
            "completed": False
        }

        # Act: Update with Unicode
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Unicode accepted
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["onboarding_step"] == "设置_个人资料"

    def test_rapid_updates(self, client, mock_db, mock_user):
        """Test rapid consecutive updates."""
        # Act: Send multiple updates rapidly
        for i in range(10):
            update_data = {"step": f"step_{i}", "completed": i == 9}
            response = client.post("/api/onboarding/update", json=update_data)
            assert response.status_code == 200

        # Assert: Final state
        assert mock_user.onboarding_step == "step_9"
        assert mock_user.onboarding_completed is True

    def test_update_response_format(self, client, mock_user):
        """Test that response matches expected format."""
        # Act: Update onboarding
        update_data = {"step": "test_step", "completed": True}
        response = client.post("/api/onboarding/update", json=update_data)

        # Assert: Verify response structure
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "message" in data
        assert isinstance(data["success"], bool)
        assert isinstance(data["data"], dict)
        assert "onboarding_step" in data["data"]
        assert "onboarding_completed" in data["data"]
        assert isinstance(data["message"], str)

    def test_status_response_format(self, client):
        """Test that status response matches expected format."""
        # Act: Get status
        response = client.get("/api/onboarding/status")

        # Assert: Verify response structure
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert isinstance(data["success"], bool)
        assert isinstance(data["data"], dict)
        assert "onboarding_step" in data["data"]
        assert "onboarding_completed" in data["data"]


# =============================================================================
# Test Branch Coverage
# =============================================================================

class TestOnboardingBranchCoverage:
    """Tests for branch coverage - testing all conditional paths."""

    def test_branch_step_is_not_none(self, client, mock_db, mock_user):
        """Test branch where step is not None."""
        update_data = {"step": "profile_setup", "completed": None}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        assert mock_user.onboarding_step == "profile_setup"

    def test_branch_step_is_none(self, client, mock_db, mock_user):
        """Test branch where step is None."""
        mock_user.onboarding_step = "original_step"
        update_data = {"step": None, "completed": True}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        # Step should not change when None
        assert mock_user.onboarding_step == "original_step"

    def test_branch_completed_is_not_none(self, client, mock_db, mock_user):
        """Test branch where completed is not None."""
        update_data = {"step": None, "completed": True}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        assert mock_user.onboarding_completed is True

    def test_branch_completed_is_none(self, client, mock_db, mock_user):
        """Test branch where completed is None."""
        mock_user.onboarding_completed = True
        update_data = {"step": "test", "completed": None}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        # Completed should not change when None
        assert mock_user.onboarding_completed is True

    def test_branch_both_fields_none(self, client, mock_db, mock_user):
        """Test branch where both step and completed are None."""
        update_data = {"step": None, "completed": None}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        # Database should still be committed (no-op but valid)

    def test_branch_both_fields_not_none(self, client, mock_db, mock_user):
        """Test branch where both step and completed are not None."""
        update_data = {"step": "final_step", "completed": True}
        response = client.post("/api/onboarding/update", json=update_data)

        assert response.status_code == 200
        assert mock_user.onboarding_step == "final_step"
        assert mock_user.onboarding_completed is True
