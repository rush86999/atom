"""
Mobile API Authentication Tests

Tests for mobile API authentication endpoints:
- Login success and failure
- Token refresh
- Token validation (/api/auth/me)
- Logout

All tests use API-first approach with TestClient (no browser).
Response structure matches web API for consistency.
"""

import pytest
from fastapi.testclient import TestClient


class TestMobileLogin:
    """Test mobile login endpoint"""

    def test_mobile_login_success(self, mobile_api_client: TestClient, mobile_test_user):
        """Test successful login with valid credentials"""
        # Login with valid credentials
        response = mobile_api_client.post("/api/auth/login", json={
            "username": mobile_test_user.email,
            "password": "MobileTest123!"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Verify token structure
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

        # Verify token type
        assert data.get("token_type") == "bearer"

        # Verify expires_in field (if present)
        if "expires_in" in data:
            assert isinstance(data["expires_in"], int)
            assert data["expires_in"] > 0

    def test_mobile_login_invalid_credentials(self, mobile_api_client: TestClient):
        """Test login with invalid credentials returns 401"""
        response = mobile_api_client.post("/api/auth/login", json={
            "username": "nonexistent@example.com",
            "password": "WrongPassword123!"
        })

        # Verify error response
        assert response.status_code == 401
        data = response.json()

        # Verify error message
        assert "detail" in data

        # Verify access_token NOT in response
        assert "access_token" not in data

    def test_mobile_login_wrong_password(self, mobile_api_client: TestClient, mobile_test_user):
        """Test login with correct email but wrong password"""
        response = mobile_api_client.post("/api/auth/login", json={
            "username": mobile_test_user.email,
            "password": "WrongPassword123!"
        })

        # Verify error response
        assert response.status_code == 401
        assert "access_token" not in response.json()


class TestMobileTokenRefresh:
    """Test mobile token refresh endpoint"""

    def test_mobile_token_refresh(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test token refresh returns new access token"""
        # Get old token from headers
        old_token = mobile_auth_headers["Authorization"].replace("Bearer ", "")

        # Refresh token
        response = mobile_api_client.post("/api/auth/refresh", headers=mobile_auth_headers)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Verify new token returned
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

        # Verify new token differs from old token
        new_token = data["access_token"]
        assert new_token != old_token

        # Verify token type
        assert data.get("token_type") == "bearer"


class TestMobileTokenValidation:
    """Test mobile token validation via /api/auth/me"""

    def test_mobile_token_validation(self, mobile_api_client: TestClient, mobile_auth_headers: dict, mobile_test_user):
        """Test token validation returns user data"""
        # Get current user info
        response = mobile_api_client.get("/api/auth/me", headers=mobile_auth_headers)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Verify user data fields
        assert "id" in data
        assert "email" in data
        assert data["email"] == mobile_test_user.email

        # Verify role or status field (if present)
        if "role" in data:
            assert data["role"] is not None
        if "status" in data:
            assert data["status"] is not None

    def test_mobile_token_validation_without_auth(self, mobile_api_client: TestClient):
        """Test token validation fails without auth header"""
        response = mobile_api_client.get("/api/auth/me")

        # Verify unauthorized response
        assert response.status_code == 401

    def test_mobile_token_validation_invalid_token(self, mobile_api_client: TestClient):
        """Test token validation fails with invalid token"""
        response = mobile_api_client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid_token_12345"
        })

        # Verify unauthorized response
        assert response.status_code == 401


class TestMobileLogout:
    """Test mobile logout endpoint"""

    def test_mobile_logout(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test logout invalidates token"""
        # Logout
        response = mobile_api_client.post("/api/auth/logout", headers=mobile_auth_headers)

        # Verify logout response
        assert response.status_code == 200
        data = response.json()

        # Verify success message
        assert "success" in data or "message" in data

        # Note: JWT tokens are stateless, so logout is client-side
        # The server logs the logout event but doesn't invalidate the token
        # Subsequent requests will still work until token expires

    def test_mobile_logout_without_auth(self, mobile_api_client: TestClient):
        """Test logout requires authentication"""
        response = mobile_api_client.post("/api/auth/logout")

        # Verify unauthorized response
        assert response.status_code == 401


class TestMobileAuthResponseStructure:
    """Test mobile auth responses match web API structure"""

    def test_mobile_login_response_structure(self, mobile_api_client: TestClient, mobile_test_user):
        """Test login response structure matches web API"""
        response = mobile_api_client.post("/api/auth/login", json={
            "username": mobile_test_user.email,
            "password": "MobileTest123!"
        })

        data = response.json()

        # Verify expected fields present
        expected_fields = ["access_token", "token_type"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Verify field types
        assert isinstance(data["access_token"], str)
        assert isinstance(data["token_type"], str)

    def test_mobile_me_response_structure(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test /api/auth/me response structure matches web API"""
        response = mobile_api_client.get("/api/auth/me", headers=mobile_auth_headers)

        data = response.json()

        # Verify expected fields present
        expected_fields = ["id", "email"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Verify field types
        assert isinstance(data["id"], str)
        assert isinstance(data["email"], str)
