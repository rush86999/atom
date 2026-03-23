"""
Admin Authorization Security Tests

Tests cover:
- Super admin role requirement for administrative endpoints
- Standard user access denial to admin endpoints
- WebSocket management authorization
- Rating sync authorization
- Conflict management authorization
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories.user_factory import UserFactory
from tests.security.conftest import create_test_token


class TestWebSocketManagementAuthorization:
    """Test WebSocket management endpoint authorization."""

    def test_websocket_status_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that websocket status endpoint requires super_admin role."""
        # Create a standard member user
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        # Try to access websocket status as standard user
        response = client.get(
            "/api/admin/websocket/status",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied with 403
        assert response.status_code == 403
        # Check that response contains permission/super_admin related error
        error_detail = response.json()
        if isinstance(error_detail, dict):
            detail = error_detail.get("detail", "")
            assert "super_admin" in str(detail).lower() or "permission" in str(detail).lower()

    def test_websocket_disable_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that websocket disable endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/websocket/disable",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_websocket_enable_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that websocket enable endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/websocket/enable",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_websocket_reconnect_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that websocket reconnect endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/websocket/reconnect",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403


class TestRatingSyncAuthorization:
    """Test rating sync endpoint authorization."""

    def test_trigger_rating_sync_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that rating sync endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/sync/ratings",
            json={"upload_all": False},
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_get_failed_rating_uploads_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that failed uploads endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.get(
            "/api/admin/ratings/failed-uploads",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_retry_failed_rating_upload_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that retry upload endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/ratings/failed-uploads/test-id/retry",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403


class TestConflictManagementAuthorization:
    """Test conflict management endpoint authorization."""

    def test_list_conflicts_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that list conflicts endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.get(
            "/api/admin/conflicts",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_get_conflict_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that get conflict endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.get(
            "/api/admin/conflicts/1",
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_resolve_conflict_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that resolve conflict endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/conflicts/1/resolve",
            json={
                "strategy": "remote_wins",
                "resolved_by": "admin@example.com"
            },
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403

    def test_bulk_resolve_conflicts_requires_super_admin(self, client: TestClient, db_session: Session):
        """Test that bulk resolve conflicts endpoint requires super_admin role."""
        standard_user = UserFactory(
            email="standard@test.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/admin/conflicts/bulk-resolve",
            json={
                "conflict_ids": [1, 2, 3],
                "strategy": "remote_wins",
                "resolved_by": "admin@example.com"
            },
            headers={"Authorization": f"Bearer {create_test_token(standard_user.id)}"}
        )

        # Should be denied
        assert response.status_code == 403


class TestAdminAuthorizationBypassAttempts:
    """Test that various user roles cannot bypass admin authorization."""

    @pytest.mark.parametrize("role", ["member", "admin", "viewer", "editor"])
    def test_non_super_admin_roles_denied_websocket_access(self, client: TestClient, db_session: Session, role: str):
        """Test that all non-super_admin roles are denied access to websocket endpoints."""
        # Create user with different role
        user = UserFactory(
            email=f"{role}@test.com",
            role=role,
            _session=db_session
        )

        response = client.get(
            "/api/admin/websocket/status",
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be denied for all non-super_admin roles
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["member", "admin", "viewer", "editor"])
    def test_non_super_admin_roles_denied_conflict_access(self, client: TestClient, db_session: Session, role: str):
        """Test that all non-super_admin roles are denied access to conflict endpoints."""
        user = UserFactory(
            email=f"{role}@test.com",
            role=role,
            _session=db_session
        )

        response = client.get(
            "/api/admin/conflicts",
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be denied for all non-super_admin roles
        assert response.status_code == 403


class TestUnauthenticatedAccess:
    """Test that unauthenticated requests are denied."""

    def test_websocket_status_requires_authentication(self, client: TestClient):
        """Test that websocket status endpoint requires authentication."""
        response = client.get("/api/admin/websocket/status")
        assert response.status_code in [401, 403]

    def test_conflict_list_requires_authentication(self, client: TestClient):
        """Test that conflict list endpoint requires authentication."""
        response = client.get("/api/admin/conflicts")
        assert response.status_code in [401, 403]

    def test_rating_sync_requires_authentication(self, client: TestClient):
        """Test that rating sync endpoint requires authentication."""
        response = client.post("/api/admin/sync/ratings", json={})
        assert response.status_code in [401, 403]
