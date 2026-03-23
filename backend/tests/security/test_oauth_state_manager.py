"""
OAuth State Manager Security Tests

Tests cover:
- State parameter generation
- State parameter validation
- Checksum verification (tamper detection)
- Expiration handling
- User binding validation
- CSRF prevention
"""
import os
import pytest
import time
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Set SECRET_KEY before importing oauth_state_manager
os.environ["SECRET_KEY"] = "test_secret_key_for_oauth_state_manager_tests"

from core.oauth_state_manager import OAuthStateManager, get_oauth_state_manager


@pytest.fixture(autouse=True)
def reset_oauth_state_manager():
    """Reset the OAuth state manager before each test."""
    import core.oauth_state_manager
    core.oauth_state_manager._oauth_state_manager = None
    yield
    core.oauth_state_manager._oauth_state_manager = None


class TestOAuthStateManager:
    """Test OAuth state manager security features."""

    def test_state_generation_produces_unique_values(self):
        """Test that state generation produces cryptographically unique values."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # Generate multiple states
        states = [manager.generate_state(user_id="test_user") for _ in range(100)]

        # All states should be unique
        assert len(set(states)) == 100, "State generation should produce unique values"

        # States should have sufficient length (for entropy)
        for state in states:
            assert len(state) > 50, f"State too short: {len(state)}"

    def test_state_with_valid_checksum_passes_validation(self):
        """Test that valid state with correct checksum passes validation."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        state = manager.generate_state(user_id="test_user")

        # Should validate successfully
        result = manager.validate_state(state, user_id="test_user", require_user_match=True)

        assert result["valid"] is True
        assert result["user_id"] == "test_user"
        assert result["expired"] is False
        assert result["tampered"] is False

    def test_state_with_tampered_checksum_fails_validation(self):
        """Test that tampered state fails validation."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        state = manager.generate_state(user_id="test_user")

        # Tamper with the state
        parts = state.split(":")
        parts[-1] = "tampered_checksum"  # Modify checksum
        tampered_state = ":".join(parts)

        # Should fail validation
        with pytest.raises(ValueError) as exc_info:
            manager.validate_state(tampered_state, user_id="test_user")

        assert "tampered" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_state_expires_after_ttl(self):
        """Test that state expires after TTL."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # Generate state with very short TTL (1 second)
        state = manager.generate_state(user_id="test_user", ttl=1)

        # Should validate immediately
        result = manager.validate_state(state, user_id="test_user")
        assert result["valid"] is True

        # Wait for expiration
        time.sleep(2)

        # Should fail after expiration
        with pytest.raises(ValueError) as exc_info:
            manager.validate_state(state, user_id="test_user")

        assert "expired" in str(exc_info.value).lower()

    def test_state_user_binding_enforces_match(self):
        """Test that state user binding enforces user ID match."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # Generate state for user1
        state = manager.generate_state(user_id="user1")

        # Should fail when validating with different user
        with pytest.raises(ValueError) as exc_info:
            manager.validate_state(state, user_id="user2", require_user_match=True)

        assert "different user" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()

    def test_state_without_user_binding_allows_any_user(self):
        """Test that state without user binding doesn't enforce user match."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # Generate state without user binding
        state = manager.generate_state(user_id=None)

        # Should validate for any user when require_user_match=False
        result = manager.validate_state(state, user_id="any_user", require_user_match=False)
        assert result["valid"] is True
        assert result["user_id"] is None

    def test_missing_state_raises_error(self):
        """Test that missing state parameter raises error."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        with pytest.raises(ValueError) as exc_info:
            manager.validate_state("")

        assert "missing" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_malformed_state_raises_error(self):
        """Test that malformed state raises error."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        malformed_states = [
            "invalid",
            "too:short",
            "also:too:short",
            "",  # Empty
        ]

        for malformed_state in malformed_states:
            with pytest.raises(ValueError):
                manager.validate_state(malformed_state)

    def test_future_timestamp_detection(self):
        """Test that state with future timestamp is rejected."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # Create a state with future timestamp (simulate time travel)
        import time
        future_time = int(time.time()) + 3600  # 1 hour in future

        # Manually construct a state with future timestamp
        import secrets
        random_token = secrets.token_urlsafe(32)
        checksum = manager._compute_checksum(random_token, future_time, "test_user")
        future_state = f"{random_token}:{future_time}:test_user:{checksum}"

        # Should reject future timestamp
        with pytest.raises(ValueError) as exc_info:
            manager.validate_state(future_state, user_id="test_user")

        # Should mention invalid or future timestamp
        error_msg = str(exc_info.value).lower()
        assert "timestamp" in error_msg or "invalid" in error_msg

    def test_different_managers_with_different_secrets_fail(self):
        """Test that states from one secret can't be validated with another."""
        manager1 = OAuthStateManager(secret_key="secret1")
        manager2 = OAuthStateManager(secret_key="secret2")

        # Generate state with secret1
        state = manager1.generate_state(user_id="test_user")

        # Try to validate with secret2
        with pytest.raises(ValueError) as exc_info:
            manager2.validate_state(state, user_id="test_user")

        # Should fail due to checksum mismatch
        assert "tampered" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_extract_user_id_from_state(self):
        """Test extracting user ID from state without validation."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        # State with user
        state_with_user = manager.generate_state(user_id="test_user")
        user_id = manager.extract_user_id(state_with_user)
        assert user_id == "test_user"

        # State without user
        state_without_user = manager.generate_state(user_id=None)
        user_id = manager.extract_user_id(state_without_user)
        assert user_id is None

    def test_checksum_is_deterministic(self):
        """Test that checksum generation is deterministic for same inputs."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        token = "test_token"
        timestamp = 1234567890
        user_id = "test_user"

        checksum1 = manager._compute_checksum(token, timestamp, user_id)
        checksum2 = manager._compute_checksum(token, timestamp, user_id)

        assert checksum1 == checksum2, "Checksum generation should be deterministic"

    def test_checksum_differs_for_different_inputs(self):
        """Test that checksum differs for different inputs."""
        manager = OAuthStateManager(secret_key="test_secret_key")

        checksum1 = manager._compute_checksum("token1", 1234567890, "user1")
        checksum2 = manager._compute_checksum("token2", 1234567890, "user1")
        checksum3 = manager._compute_checksum("token1", 1234567891, "user1")
        checksum4 = manager._compute_checksum("token1", 1234567890, "user2")

        # All checksums should be different
        assert checksum1 != checksum2, "Checksum should differ for different tokens"
        assert checksum1 != checksum3, "Checksum should differ for different timestamps"
        assert checksum1 != checksum4, "Checksum should differ for different users"


class TestSlackOAuthCallbackSecurity:
    """Test Slack OAuth callback security with state validation."""

    @pytest.fixture
    def authenticated_user(self, db_session: Session):
        """Create an authenticated user for testing."""
        from tests.factories.user_factory import UserFactory
        return UserFactory(_session=db_session)

    def test_callback_requires_state_parameter(self, client: TestClient, authenticated_user):
        """Test that callback requires state parameter."""
        from tests.security.conftest import create_test_token

        response = client.post(
            "/api/slack/callback",
            json={"code": "valid_auth_code"},
            headers={"Authorization": f"Bearer {create_test_token(authenticated_user.id)}"}
        )

        # Should reject request without state
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

    def test_callback_requires_authentication(self, client: TestClient):
        """Test that callback requires authentication."""
        response = client.post(
            "/api/slack/callback",
            json={
                "code": "valid_auth_code",
                "state": "some_state"
            }
        )

        # Should reject unauthenticated request
        assert response.status_code in [401, 403]

    def test_callback_validates_state_checksum(self, client: TestClient, authenticated_user):
        """Test that callback validates state checksum."""
        from tests.security.conftest import create_test_token

        # Create tampered state
        manager = get_oauth_state_manager()
        valid_state = manager.generate_state(user_id=str(authenticated_user.id))

        # Tamper with state
        parts = valid_state.split(":")
        parts[-1] = "tampered_checksum"
        tampered_state = ":".join(parts)

        response = client.post(
            "/api/slack/callback",
            json={
                "code": "valid_auth_code",
                "state": tampered_state
            },
            headers={"Authorization": f"Bearer {create_test_token(authenticated_user.id)}"}
        )

        # Should reject tampered state
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    @patch('core.oauth_handler.OAuthHandler.exchange_code_for_tokens')
    def test_callback_succeeds_with_valid_state(self, mock_exchange, client: TestClient, authenticated_user, db_session: Session):
        """Test that callback succeeds with valid state."""
        from tests.security.conftest import create_test_token

        # Mock successful token exchange
        mock_exchange.return_value = {
            "access_token": "slack_access_token",
            "refresh_token": "slack_refresh_token",
            "expires_in": 3600
        }

        # Generate valid state
        manager = get_oauth_state_manager()
        state = manager.generate_state(user_id=str(authenticated_user.id))

        response = client.post(
            "/api/slack/callback",
            json={
                "code": "valid_auth_code",
                "state": state
            },
            headers={"Authorization": f"Bearer {create_test_token(authenticated_user.id)}"}
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "connection_id" in data

    def test_auth_url_generates_state(self, client: TestClient, authenticated_user):
        """Test that auth URL endpoint generates state parameter."""
        from tests.security.conftest import create_test_token

        response = client.get(
            "/api/slack/auth/url",
            headers={"Authorization": f"Bearer {create_test_token(authenticated_user.id)}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should include state parameter
        assert "state" in data
        assert len(data["state"]) > 50  # Should have sufficient entropy
        assert "url" in data

        # State should be validatable
        manager = get_oauth_state_manager()
        result = manager.validate_state(data["state"], user_id=str(authenticated_user.id), require_user_match=True)
        assert result["valid"] is True

    def test_auth_url_requires_authentication(self, client: TestClient):
        """Test that auth URL endpoint requires authentication."""
        response = client.get("/api/slack/auth/url")

        # Should reject unauthenticated request
        assert response.status_code in [401, 403]


class TestCSRFPrevention:
    """Test CSRF prevention through state parameter."""

    def test_csrf_attack_prevented(self, client: TestClient, db_session: Session):
        """
        Test that CSRF attack is prevented.

        Scenario:
        1. Attacker initiates OAuth flow and gets auth code for their account
        2. Attacker tries to send that code to victim's callback
        3. Should fail because state doesn't match victim's session
        """
        from tests.factories.user_factory import UserFactory
        from tests.security.conftest import create_test_token

        # Create victim user
        victim = UserFactory(email="victim@example.com", _session=db_session)

        # Attacker generates their own state
        manager = get_oauth_state_manager()
        attacker_state = manager.generate_state(user_id="attacker_user_id")

        # Attacker tries to use victim's callback with their state
        response = client.post(
            "/api/slack/callback",
            json={
                "code": "attacker_stolen_code",
                "state": attacker_state
            },
            headers={"Authorization": f"Bearer {create_test_token(victim.id)}"}
        )

        # Should reject because state user_id doesn't match victim
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower() or "user" in response.json()["detail"].lower()
