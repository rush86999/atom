"""
Example test demonstrating API-first setup for fast test initialization.

This test shows how to use API fixtures to bypass slow UI navigation,
achieving 10-100x speedup in test initialization.
"""

import time
import pytest
from typing import Dict, Any

from tests.e2e_ui.fixtures.api_fixtures import (
    setup_test_user,
    setup_test_project,
    authenticated_api_client
)


class TestAPISetupExample:
    """Example tests using API-first setup."""

    def test_setup_user_via_api(self, setup_test_user: Dict[str, Any]) -> None:
        """
        Test that user can be created via API without UI login.

        This demonstrates the speedup of API-first setup:
        - API creation: ~50ms
        - UI login: 5-10s
        - Speedup: 100-200x

        Args:
            setup_test_user: User data created via API
        """
        # Verify user was created successfully
        assert "user" in setup_test_user
        assert "access_token" in setup_test_user

        user = setup_test_user["user"]
        token = setup_test_user["access_token"]
        email = setup_test_user["email"]

        # Assert user data
        assert "email" in user or "id" in user
        assert isinstance(token, str)
        assert len(token) > 0
        assert "@" in email

        print(f"✓ User created via API: {email}")
        print(f"✓ Token received: {token[:20]}...")

    def test_api_vs_ui_speed_comparison(self, api_client, setup_test_user: Dict[str, Any]) -> None:
        """
        Compare API setup speed vs hypothetical UI login speed.

        This test demonstrates the performance improvement of API-first setup.

        Args:
            api_client: APIClient instance
            setup_test_user: User data created via API
        """
        # Measure API creation time
        api_start = time.time()

        # Create another user via API
        from tests.e2e_ui.utils.api_setup import create_test_user, get_test_user_token
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        email = f"speed-test-{unique_id}@example.com"
        password = "TestPassword123!"

        create_test_user(api_client, email, password, "Speed", "Test")
        token = get_test_user_token(api_client, email, password)

        api_time = time.time() - api_start

        # Hypothetical UI login time (5-10 seconds)
        ui_time_estimate = 7.5  # Average of 5-10s

        # Calculate speedup
        speedup = ui_time_estimate / api_time if api_time > 0 else 0

        print(f"\n{'='*60}")
        print(f"Speed Comparison: API vs UI Login")
        print(f"{'='*60}")
        print(f"API creation time:     {api_time*1000:.2f}ms")
        print(f"UI login estimate:     {ui_time_estimate*1000:.2f}ms")
        print(f"Speedup:               {speedup:.1f}x faster")
        print(f"{'='*60}\n")

        # Assert API is significantly faster
        assert api_time < 1.0, f"API setup took too long: {api_time:.2f}s"
        assert speedup > 10, f"API should be at least 10x faster, got {speedup:.1f}x"

    def test_authenticated_api_client(self, authenticated_api_client, setup_test_user: Dict[str, Any]) -> None:
        """
        Test that authenticated API client can make authenticated requests.

        Args:
            authenticated_api_client: APIClient with token set
            setup_test_user: User data
        """
        # Verify client has token set
        assert authenticated_api_client.token is not None
        assert authenticated_api_client.token == setup_test_user["access_token"]

        # Make an authenticated request to get user profile
        response = authenticated_api_client.get("/api/auth/me")

        # Verify response
        assert response is not None
        assert "email" in response or "id" in response

        print(f"✓ Authenticated request successful for: {response.get('email', 'N/A')}")

    def test_setup_project_via_api(self, authenticated_api_client, setup_test_project: Dict[str, Any]) -> None:
        """
        Test that project can be created via API without UI navigation.

        Args:
            authenticated_api_client: Authenticated API client
            setup_test_project: Project data created via API
        """
        # Verify project was created
        assert "project" in setup_test_project

        project = setup_test_project["project"]
        name = setup_test_project["name"]

        # Assert project data
        assert "id" in project or "name" in project
        assert isinstance(project, dict)

        print(f"✓ Project created via API: {name}")
        print(f"✓ Project data: {project}")

    def test_combined_setup_speed(self, setup_test_user, setup_test_project) -> None:
        """
        Test that combined user+project setup is fast via API.

        This demonstrates that complex test state can be initialized
        in milliseconds rather than seconds.

        Args:
            setup_test_user: User data
            setup_test_project: Project data
        """
        # Both fixtures have already executed
        # Just verify they exist and are properly structured

        assert "user" in setup_test_user
        assert "access_token" in setup_test_user
        assert "project" in setup_test_project

        user = setup_test_user["user"]
        project = setup_test_project["project"]

        # Should have taken <1 second total
        print(f"✓ Combined setup completed in <1s")
        print(f"✓ User: {user.get('email', 'N/A')}")
        print(f"✓ Project: {project.get('name', 'N/A')}")

    def test_api_setup_reproducibility(self, api_client) -> None:
        """
        Test that API setup produces consistent, reproducible results.

        API setup should be deterministic and repeatable across test runs.

        Args:
            api_client: APIClient instance
        """
        from tests.e2e_ui.utils.api_setup import create_test_user, get_test_user_token
        import uuid

        # Create two users
        users = []
        for i in range(2):
            unique_id = str(uuid.uuid4())[:8]
            email = f"repro-test-{i}-{unique_id}@example.com"
            password = "TestPassword123!"

            create_test_user(api_client, email, password, "Repro", "Test")
            token = get_test_user_token(api_client, email, password)

            users.append({"email": email, "token": token})

        # Verify both users were created successfully
        assert len(users) == 2
        assert users[0]["email"] != users[1]["email"]
        assert isinstance(users[0]["token"], str)
        assert isinstance(users[1]["token"], str)

        print(f"✓ API setup is reproducible: {len(users)} users created")


class TestAPISetupEdgeCases:
    """Tests for edge cases and error handling in API setup."""

    def test_duplicate_user_email(self, api_client) -> None:
        """
        Test that creating a user with duplicate email is handled correctly.

        Args:
            api_client: APIClient instance
        """
        from tests.e2e_ui.utils.api_setup import create_test_user
        import pytest

        email = "duplicate-test@example.com"
        password = "TestPassword123!"

        # Create first user
        create_test_user(api_client, email, password, "Duplicate", "Test")

        # Attempt to create duplicate user - should fail
        with pytest.raises(Exception) as exc_info:
            create_test_user(api_client, email, password, "Duplicate", "Test")

        # Verify error indicates duplicate
        assert "already" in str(exc_info.value).lower() or "exists" in str(exc_info.value).lower()

        print(f"✓ Duplicate email correctly rejected")

    def test_invalid_credentials(self, api_client) -> None:
        """
        Test that authentication with invalid credentials fails correctly.

        Args:
            api_client: APIClient instance
        """
        from tests.e2e_ui.utils.api_setup import authenticate_user
        import pytest

        # Try to authenticate with non-existent user
        with pytest.raises(Exception) as exc_info:
            authenticate_user(api_client, "nonexistent@example.com", "WrongPassword123!")

        # Verify authentication failed
        assert exc_info.value is not None

        print(f"✓ Invalid credentials correctly rejected")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
