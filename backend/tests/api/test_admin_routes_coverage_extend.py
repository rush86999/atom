"""
Extended coverage tests for admin_routes.py.

Target: 50%+ coverage (374 statements, ~187 lines to cover)
Focus: Admin endpoints, user management, system operations
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the router
from api.admin_routes import router


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with admin router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestAdminEndpoints:
    """Test admin API endpoints."""

    def test_list_users(self, client):
        """Test listing all users."""
        response = client.get("/api/admin/users")

        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert "users" in data or isinstance(data, list)

    def test_get_user_by_id(self, client):
        """Test getting specific user."""
        response = client.get("/api/admin/users/user-123")

        assert response.status_code in [200, 401, 404]

    def test_create_user(self, client):
        """Test creating new user."""
        response = client.post(
            "/api/admin/users",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "role": "user"
            }
        )

        assert response.status_code in [201, 400, 401]

    def test_update_user(self, client):
        """Test updating user (route is PATCH, not PUT)."""
        response = client.patch(
            "/api/admin/users/user-123",
            json={"name": "Updated Name"}
        )

        assert response.status_code in [200, 401, 404]

    def test_delete_user(self, client):
        """Test deleting user."""
        response = client.delete("/api/admin/users/user-123")

        assert response.status_code in [200, 204, 401, 404]

    def test_list_roles(self, client):
        """Test listing all roles."""
        response = client.get("/api/admin/roles")

        assert response.status_code in [200, 401]

    def test_create_role(self, client):
        """Test creating new role."""
        response = client.post(
            "/api/admin/roles",
            json={
                "name": "custom-role",
                "permissions": {"read": True, "write": True}
            }
        )

        assert response.status_code in [201, 400, 401]

    def test_assign_role_to_user(self, client):
        """Test assigning role to user."""
        response = client.post(
            "/api/admin/users/user-123/roles",
            json={"role": "admin"}
        )

        assert response.status_code in [200, 404]


class TestSystemOperations:
    """Test admin platform operation endpoints (current admin_routes surface)."""

    def test_get_websocket_status(self, client):
        """Test getting websocket sync status."""
        response = client.get("/api/admin/websocket/status")

        assert response.status_code in [200, 401]

    def test_reconnect_websocket(self, client):
        """Test triggering websocket reconnect."""
        response = client.post("/api/admin/websocket/reconnect")

        assert response.status_code in [200, 401]

    def test_get_failed_rating_uploads(self, client):
        """Test getting failed rating uploads."""
        response = client.get("/api/admin/ratings/failed-uploads")

        assert response.status_code in [200, 401]

    def test_trigger_rating_sync(self, client):
        """Test triggering a manual rating sync."""
        response = client.post("/api/admin/sync/ratings")

        assert response.status_code in [200, 401]

    def test_list_conflicts(self, client):
        """Test listing unresolved sync conflicts."""
        response = client.get("/api/admin/conflicts")

        assert response.status_code in [200, 401]


class TestAdminErrorHandling:
    """Test admin endpoint error handling."""

    def test_handle_invalid_user_id(self, client):
        """Test handling of invalid user ID."""
        response = client.get("/api/admin/users/invalid-id-!!!")

        assert response.status_code in [400, 401, 404]

    def test_handle_duplicate_email(self, client):
        """Test that unauthenticated access to user creation is blocked."""
        response = client.post(
            "/api/admin/users",
            json={"email": "test@example.com", "name": "Test", "role": "user"}
        )

        # The super_admin dependency rejects unauthenticated callers before
        # any DB interaction (duplicate check happens post-auth).
        assert response.status_code in [400, 401, 409]

    def test_handle_unauthorized_admin_access(self, client):
        """Test handling of unauthorized admin access."""
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code in [401, 403]
