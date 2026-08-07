"""
Test OAuth Token Storage Implementation

Tests for the unified OAuth state and token storage models and methods.
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.models import OAuthState, IntegrationToken
from core.database import get_db_session


@pytest.fixture(scope="function")
def test_db():
    """Use production database pattern for testing"""
    with get_db_session() as db:
        yield db

        # Cleanup after test
        db.query(IntegrationToken).delete()
        db.query(OAuthState).delete()
        db.commit()


class TestOAuthState:
    """Test OAuth state model for CSRF protection"""

    def test_oauth_state_model_exists(self):
        """Test that OAuthState model can be imported"""
        from core.models import OAuthState
        assert OAuthState is not None
        assert OAuthState.__tablename__ == "oauth_states"

    def test_oauth_token_model_exists(self):
        """Test that IntegrationToken model can be imported"""
        from core.models import IntegrationToken
        assert IntegrationToken is not None
        assert IntegrationToken.__tablename__ == "integration_tokens"


class TestOAuthTokenExpiration:
    """Test integration token expiration logic.

    IntegrationToken is the provider-scoped token store with is_expired()/
    is_valid(); the OAuth-server OAuthToken model stores hashes only.
    """

    def test_is_expired_with_past_date(self):
        """Test is_expired() returns True for expired tokens"""
        token = IntegrationToken(
            id=str(uuid4()),
            tenant_id="default",
            user_id=str(uuid4()),
            provider="google",
            access_token="test_token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            status="active"
        )

        assert token.is_expired() is True

    def test_is_expired_with_future_date(self):
        """Test is_expired() returns False for valid tokens"""
        token = IntegrationToken(
            id=str(uuid4()),
            tenant_id="default",
            user_id=str(uuid4()),
            provider="google",
            access_token="test_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status="active"
        )

        assert token.is_expired() is False

    def test_is_expired_with_none_expiration(self):
        """Test is_expired() returns False for tokens without expiration (like Notion)"""
        token = IntegrationToken(
            id=str(uuid4()),
            tenant_id="default",
            user_id=str(uuid4()),
            provider="notion",
            access_token="test_token",
            expires_at=None,
            status="active"
        )

        assert token.is_expired() is False


class TestOAuthModelRepr:
    """Test model __repr__ methods"""

    def test_oauth_state_repr(self):
        """Test OAuthState __repr__ method"""
        state = OAuthState(
            id="test-id",
            tenant_id="default",
            user_id="user-123",
            provider="google",
            state="state-token",
            expires_at=datetime.now() + timedelta(minutes=10),
        )

        repr_str = repr(state)
        assert "OAuthState" in repr_str
        assert "test-id" in repr_str
        assert "google" in repr_str
        assert "state-to" in repr_str  # state is truncated to 8 chars in repr

    def test_oauth_token_repr(self):
        """Test IntegrationToken __repr__ method"""
        token = IntegrationToken(
            id="token-id",
            tenant_id="default",
            user_id="user-123",
            provider="slack",
            access_token="xoxb-test",
            status="active"
        )

        repr_str = repr(token)
        assert "IntegrationToken" in repr_str
        assert "token-id" in repr_str
        assert "slack" in repr_str
        assert "active" in repr_str
