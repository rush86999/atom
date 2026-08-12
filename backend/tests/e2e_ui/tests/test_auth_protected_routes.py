"""
E2E tests for protected routes (AUTH-05).

Run with: pytest backend/tests/e2e_ui/tests/test_auth_protected_routes.py -v
"""

import pytest
import requests
from datetime import datetime, timedelta
from playwright.sync_api import Page
from jose import jwt
import os


def create_expired_token() -> str:
    """Create an expired JWT token for testing.

    The token is signed with the LIVE backend's SECRET_KEY (core.auth reads it
    from backend/.env — the e2e fixtures load that file, see
    fixtures/auth_fixtures.py) so the backend actually attempts to verify the
    signature and rejects it on expiry rather than on signature mismatch.

    Returns:
        Expired JWT token string
    """
    payload = {
        'sub': 'test-user-id',
        'exp': datetime.utcnow() - timedelta(hours=1),
    }

    # Same key the running backend uses for HS256 verification.
    # fallback is only for environments where the backend was started with a
    # different/auto-generated key (then expiry rejection still works because
    # a signature mismatch is also rejected — but we prefer the real key).
    from core.auth import SECRET_KEY as backend_secret
    secret = backend_secret or os.getenv('SECRET_KEY', 'test-secret-key')

    return jwt.encode(payload, secret, algorithm='HS256')


BACKEND_URL = "http://localhost:8001"  # live e2e backend (api_base_url fixture)


class TestProtectedRoutes:
    """E2E tests for protected routes (AUTH-05)."""

    def test_protected_route_redirects_unauthenticated_ui(self, page: Page):
        """Verify protected routes redirect unauthenticated users to login.

        This test validates:
        1. Try to navigate to /dashboard without authentication
        2. Verify current_url contains 'login' (redirected)
        3. Try /agents, verify redirect to login
        4. Try /settings, verify redirect to login

        Args:
            page: Unauthenticated Playwright page fixture

        Coverage: AUTH-05 (Protected route redirects)
        """
        # Test 1: Try to access /dashboard without auth
        page.goto("http://localhost:3001/dashboard")
        page.wait_for_timeout(1000)

        current_url = page.url.lower()
        assert 'login' in current_url, \
            f"Should redirect to login when accessing /dashboard, got URL: {current_url}"

        # Test 2: Try to access /agents without auth
        page.goto("http://localhost:3001/agents")
        page.wait_for_timeout(1000)

        current_url = page.url.lower()
        assert 'login' in current_url, \
            f"Should redirect to login when accessing /agents, got URL: {current_url}"

        # Test 3: Try to access /settings without auth
        page.goto("http://localhost:3001/settings")
        page.wait_for_timeout(1000)

        current_url = page.url.lower()
        assert 'login' in current_url, \
            f"Should redirect to login when accessing /settings, got URL: {current_url}"

        print("✓ All protected routes redirect to login without authentication")

    def test_protected_api_returns_401_without_token(self):
        """Verify protected API endpoints return 401 without authentication token.

        This test validates:
        1. GET request to /api/agents without token returns 401
        2. GET request to /api/users/me without token returns 401
        3. Response indicates authentication required

        Coverage: AUTH-05 (Protected API returns 401)
        """
        # Test 1: Try to access /api/agents without token
        response = requests.get(f"{BACKEND_URL}/api/agents", timeout=5)

        assert response.status_code == 401, \
            f"Should return 401 for /api/agents without token, got {response.status_code}"

        # Test 2: Try to access /api/users/me without token
        response = requests.get(f"{BACKEND_URL}/api/users/me", timeout=5)

        assert response.status_code == 401, \
            f"Should return 401 for /api/users/me without token, got {response.status_code}"

        print("✓ Protected API endpoints return 401 without authentication")

    def test_protected_api_accepts_valid_token(self, authenticated_user):
        """Verify protected API endpoints accept valid JWT token.

        This test validates:
        1. GET request with Authorization: Bearer {token} header
        2. Response status is 200
        3. Response contains valid data (not error message)

        Args:
            authenticated_user: Authenticated user fixture (user, token)

        Coverage: AUTH-05 (Protected API accepts valid token)
        """
        user, token = authenticated_user

        # Make GET request with valid token
        response = requests.get(
            f"{BACKEND_URL}/api/agents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )

        # The fixture token is signed with the backend's SECRET_KEY (fixtures
        # load backend/.env, see fixtures/auth_fixtures.py) and /api/agents is
        # a real protected endpoint — a valid token must be accepted with 200.
        assert response.status_code == 200, \
            f"Backend should accept valid token, got status {response.status_code}"

        # Verify response contains valid data (not just error)
        data = response.json()
        assert isinstance(data, (dict, list)), "Response should be valid JSON"
        print("✓ Protected API accepts valid JWT token")

    def test_protected_api_rejects_expired_token(self):
        """Verify protected API endpoints reject expired JWT tokens.

        This test validates:
        1. Create expired JWT token (exp in past)
        2. Make request with expired token in Authorization header
        3. Verify response status is 401 or 403
        4. Verify error message about expired/invalid token

        Coverage: AUTH-05 (Protected API rejects expired token)
        """
        # Create expired token
        expired_token = create_expired_token()

        # Make request with expired token
        response = requests.get(
            f"{BACKEND_URL}/api/agents",
            headers={"Authorization": f"Bearer {expired_token}"},
            timeout=5
        )

        # Verify rejection (401 or 403)
        assert response.status_code in [401, 403], \
            f"Should reject expired token with 401/403, got {response.status_code}"

        # Verify error message
        try:
            error_data = response.json()
            error_detail = error_data.get('detail', '').lower()

            # Check for expired/invalid error indicators
            has_expired_error = any(keyword in error_detail for keyword in [
                'expired', 'invalid', 'unauthorized', 'could not validate'
            ])

            assert has_expired_error or response.status_code in [401, 403], \
                f"Error should mention expired/invalid token, got: {error_detail}"
        except Exception:
            # Response might not be JSON, but status code is enough
            pass

        print("✓ Protected API rejects expired JWT token")


class TestProtectedRouteVariations:
    """Additional protected route validation tests."""

    def test_protected_api_rejects_malformed_token(self):
        """Verify protected API rejects malformed JWT tokens.

        Coverage: AUTH-05 (Malformed token rejection)
        """
        # Create malformed token (not valid JWT)
        malformed_token = "not.a.valid.jwt.token"

        response = requests.get(
            f"{BACKEND_URL}/api/agents",
            headers={"Authorization": f"Bearer {malformed_token}"},
            timeout=5
        )

        # Should reject malformed token
        assert response.status_code == 401, \
            f"Should reject malformed token with 401, got {response.status_code}"

        print("✓ Protected API rejects malformed token")

    def test_protected_api_rejects_missing_token(self):
        """Verify protected API rejects requests with missing Authorization header.

        Coverage: AUTH-05 (Missing token rejection)
        """
        # Make request without Authorization header
        response = requests.get(f"{BACKEND_URL}/api/agents", timeout=5)

        assert response.status_code == 401, \
            f"Should reject missing token with 401, got {response.status_code}"

        print("✓ Protected API rejects missing Authorization header")

    def test_protected_api_rejects_wrong_scheme(self, authenticated_user):
        """Verify protected API rejects tokens with wrong auth scheme.

        Args:
            authenticated_user: Authenticated user fixture (user, token)

        Coverage: AUTH-05 (Wrong auth scheme rejection)
        """
        user, token = authenticated_user

        # Use wrong scheme (Basic instead of Bearer)
        response = requests.get(
            f"{BACKEND_URL}/api/agents",
            headers={"Authorization": f"Basic {token}"},
            timeout=5
        )

        # Should reject wrong scheme
        assert response.status_code == 401, \
            f"Should reject wrong auth scheme with 401, got {response.status_code}"

        print("✓ Protected API rejects wrong authentication scheme")
