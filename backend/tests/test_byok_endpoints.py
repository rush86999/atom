"""
Tests for BYOK Endpoints - Bring Your Own Key management.

Coverage Goals (25-30% on 1300 lines):
- BYOK key management (add, remove, rotate)
- BYOK configuration (per-provider, per-agent, global)
- BYOK usage statistics and tracking
- BYOK validation (key format, permissions, quotas)
- BYOK API endpoints (REST, CRUD operations)
- Governance integration (ADMIN-only access)
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from core.models import BYOKKey, BYOKUsage


class TestBYOKKeyManagement:
    """Test BYOK key lifecycle management."""

    def test_add_openai_key(self):
        """Add OpenAI API key for user."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.byok_endpoints import add_key
        result = add_key(
            user_id="user-123",
            provider="openai",
            api_key="sk-test-12345",
            db=mock_db
        )

        assert result["provider"] == "openai"
        assert result["status"] == "active"

    def test_add_anthropic_key(self):
        """Add Anthropic API key for user."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.byok_endpoints import add_key
        result = add_key(
            user_id="user-456",
            provider="anthropic",
            api_key="sk-ant-test-12345",
            db=mock_db
        )

        assert result["provider"] == "anthropic"

    def test_remove_key(self):
        """Remove API key for user."""
        mock_db = Mock()
        mock_key = Mock()
        mock_key.id = "key-123"
        mock_key.user_id = "user-123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        from core.byok_endpoints import remove_key
        result = remove_key(
            key_id="key-123",
            user_id="user-123",
            db=mock_db
        )

        assert result["deleted"] is True

    def test_rotate_key(self):
        """Rotate existing API key with new key."""
        mock_db = Mock()
        mock_key = Mock()
        mock_key.id = "key-123"
        mock_key.api_key_hash = "old_hash"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key
        mock_db.commit = Mock()

        from core.byok_endpoints import rotate_key
        result = rotate_key(
            key_id="key-123",
            new_api_key="sk-new-key-456",
            db=mock_db
        )

        assert result["rotated"] is True


class TestBYOKConfiguration:
    """Test BYOK configuration at different scopes."""

    def test_per_provider_configuration(self):
        """Configure BYOK keys per provider."""
        mock_db = Mock()

        mock_keys = [
            Mock(provider="openai", is_active=True),
            Mock(provider="anthropic", is_active=True),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_keys
        mock_db.query.return_value.filter.return_value = mock_query

        from core.byok_endpoints import get_provider_config
        config = get_provider_config(
            user_id="user-123",
            db=mock_db
        )

        assert len(config) == 2

    def test_per_agent_configuration(self):
        """Configure BYOK keys per agent."""
        mock_db = Mock()

        mock_agent_key = Mock()
        mock_agent_key.agent_id = "agent-456"
        mock_agent_key.provider = "openai"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent_key

        from core.byok_endpoints import get_agent_config
        config = get_agent_config(
            agent_id="agent-456",
            db=mock_db
        )

        assert config["provider"] == "openai"

    def test_global_configuration(self):
        """Configure global default BYOK keys."""
        mock_db = Mock()

        mock_global_key = Mock()
        mock_global_key.provider = "openai"
        mock_global_key.is_global_default = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_global_key

        from core.byok_endpoints import get_global_config
        config = get_global_config(
            provider="openai",
            db=mock_db
        )

        assert config["is_global_default"] is True


class TestBYOKUsage:
    """Test BYOK usage tracking and statistics."""

    def test_track_usage(self):
        """Track API usage for BYOK key."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.byok_endpoints import track_usage
        usage = track_usage(
            key_id="key-123",
            request_count=1,
            token_count=1000,
            db=mock_db
        )

        assert usage["tokens_used"] == 1000

    def test_get_usage_stats(self):
        """Get usage statistics for BYOK key."""
        mock_db = Mock()

        mock_usage = Mock()
        mock_usage.total_requests = 1000
        mock_usage.total_tokens = 500000
        mock_usage.total_cost = 5.00

        mock_db.query.return_value.filter.return_value.first.return_value = mock_usage

        from core.byok_endpoints import get_usage_stats
        stats = get_usage_stats(
            key_id="key-123",
            db=mock_db
        )

        assert stats["total_requests"] == 1000
        assert stats["total_tokens"] == 500000

    def test_get_per_agent_usage(self):
        """Get usage statistics per agent."""
        mock_db = Mock()

        mock_agent_usage = [
            Mock(agent_id="agent-1", total_tokens=10000),
            Mock(agent_id="agent-2", total_tokens=15000),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.group_by.return_value.all.return_value = mock_agent_usage
        mock_db.query.return_value.filter.return_value = mock_query

        from core.byok_endpoints import get_agent_usage_stats
        stats = get_agent_usage_stats(
            user_id="user-123",
            db=mock_db
        )

        assert len(stats) == 2

    def test_get_time_based_usage(self):
        """Get usage statistics for time period."""
        mock_db = Mock()

        mock_hourly_usage = [
            Mock(hour=0, token_count=5000),
            Mock(hour=1, token_count=7000),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.group_by.return_value.all.return_value = mock_hourly_usage
        mock_db.query.return_value.filter.return_value = mock_query

        from core.byok_endpoints import get_usage_by_time
        usage = get_usage_by_time(
            key_id="key-123",
            hours=24,
            db=mock_db
        )

        assert len(usage) == 2


class TestBYOKValidation:
    """Test BYOK key validation and security."""

    def test_validate_openai_key_format(self):
        """Validate OpenAI key format (sk- prefix)."""
        from core.byok_endpoints import validate_key_format

        # Valid key
        result = validate_key_format("openai", "sk-test-12345")
        assert result["valid"] is True

        # Invalid key
        result = validate_key_format("openai", "invalid-key")
        assert result["valid"] is False

    def test_validate_anthropic_key_format(self):
        """Validate Anthropic key format (sk-ant- prefix)."""
        from core.byok_endpoints import validate_key_format

        result = validate_key_format("anthropic", "sk-ant-test-12345")
        assert result["valid"] is True

    def test_check_key_permissions(self):
        """Check if user has permission for key."""
        mock_db = Mock()

        mock_key = Mock()
        mock_key.user_id = "user-123"
        mock_key.permissions = ["read", "write"]

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        from core.byok_endpoints import check_key_permissions
        perms = check_key_permissions(
            key_id="key-123",
            user_id="user-123",
            db=mock_db
        )

        assert "read" in perms["permissions"]

    def test_enforce_quota_limits(self):
        """Enforce quota limits for API usage."""
        mock_db = Mock()

        mock_usage = Mock()
        mock_usage.total_tokens = 900000
        mock_usage.quota_limit = 1000000

        mock_db.query.return_value.filter.return_value.first.return_value = mock_usage

        from core.byok_endpoints import check_quota_limit
        result = check_quota_limit(
            key_id="key-123",
            tokens_requested=100000,
            db=mock_db
        )

        assert result["within_quota"] is True


class TestBYOKAPI:
    """Test BYOK REST API endpoints."""

    def test_post_add_key_endpoint(self):
        """Test POST /byok/keys endpoint."""
        from core.byok_endpoints import app
        client = TestClient(app)

        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('core.byok_endpoints.get_db', return_value=mock_db):
            response = client.post(
                "/byok/keys",
                json={
                    "provider": "openai",
                    "api_key": "sk-test-12345"
                },
                headers={"X-User-Id": "user-123"}
            )

            assert response.status_code == 200

    def test_get_keys_endpoint(self):
        """Test GET /byok/keys endpoint."""
        from core.byok_endpoints import app
        client = TestClient(app)

        mock_db = Mock()
        mock_keys = [Mock(id="key-1", provider="openai")]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_keys
        mock_db.query.return_value.filter.return_value = mock_query

        with patch('core.byok_endpoints.get_db', return_value=mock_db):
            response = client.get(
                "/byok/keys",
                headers={"X-User-Id": "user-123"}
            )

            assert response.status_code == 200

    def test_delete_key_endpoint(self):
        """Test DELETE /byok/keys/{key_id} endpoint."""
        from core.byok_endpoints import app
        client = TestClient(app)

        mock_db = Mock()
        mock_key = Mock()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        with patch('core.byok_endpoints.get_db', return_value=mock_db):
            response = client.delete(
                "/byok/keys/key-123",
                headers={"X-User-Id": "user-123"}
            )

            assert response.status_code == 200


class TestGovernanceEnforcement:
    """Test governance enforcement for BYOK operations."""

    def test_admin_only_access(self):
        """Only ADMIN users can access BYOK endpoints."""
        from core.byok_endpoints import check_admin_access

        # Admin user
        result = check_admin_access(user_role="ADMIN")
        assert result["allowed"] is True

        # Non-admin user
        result = check_admin_access(user_role="USER")
        assert result["allowed"] is False

    def test_autonomous_agent_access(self):
        """AUTONOMOUS agents can access BYOK keys."""
        mock_db = Mock()

        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        from core.byok_endpoints import check_agent_access
        result = check_agent_access(
            agent_id="agent-123",
            db=mock_db
        )

        assert result["allowed"] is True

    def test_student_agent_blocked(self):
        """STUDENT agents cannot access BYOK keys."""
        mock_db = Mock()

        mock_agent = Mock()
        mock_agent.status = "STUDENT"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        from core.byok_endpoints import check_agent_access
        result = check_agent_access(
            agent_id="agent-789",
            db=mock_db
        )

        assert result["allowed"] is False


class TestErrorHandling:
    """Test error handling in BYOK operations."""

    def test_key_not_found(self):
        """Return 404 when key doesn't exist."""
        mock_db = Mock()

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from core.byok_endpoints import get_key
        result = get_key(
            key_id="nonexistent-key",
            db=mock_db
        )

        assert result is None

    def test_invalid_provider(self):
        """Reject invalid provider names."""
        from core.byok_endpoints import validate_provider

        result = validate_provider("invalid_provider")
        assert result["valid"] is False

    def test_duplicate_key_detection(self):
        """Detect duplicate keys for same provider."""
        mock_db = Mock()

        mock_existing_key = Mock()
        mock_existing_key.provider = "openai"
        mock_existing_key.api_key_hash = "hash123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_key

        from core.byok_endpoints import check_duplicate_key
        result = check_duplicate_key(
            user_id="user-123",
            provider="openai",
            api_key_hash="hash123",
            db=mock_db
        )

        assert result["duplicate"] is True


class TestSecurity:
    """Test security features of BYOK system."""

    def test_key_hashing(self):
        """API keys are hashed before storage."""
        from core.byok_endpoints import hash_api_key

        key = "sk-test-12345"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)

        assert hash1 == hash2  # Same key produces same hash
        assert hash1 != key     # Hash is not the original key

    def test_key_never_logged(self):
        """API keys are never logged or exposed."""
        mock_db = Mock()

        from core.byok_endpoints import add_key
        result = add_key(
            user_id="user-123",
            provider="openai",
            api_key="sk-secret-key-12345",
            db=mock_db
        )

        # Result should not contain actual API key
        assert "sk-secret-key-12345" not in str(result)
        assert "api_key" not in result or result["api_key"] is None

    def test_key_redaction_in_logs(self):
        """Keys are redacted in logs."""
        from core.byok_endpoints import redact_key_for_logging

        key = "sk-test-12345"
        redacted = redact_key_for_logging(key)

        assert redacted.startswith("sk-")

    def test_key_rotation_invalidates_old(self):
        """Old key is invalidated after rotation."""
        mock_db = Mock()

        mock_key = Mock()
        mock_key.id = "key-123"
        mock_key.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key
        mock_db.commit = Mock()

        from core.byok_endpoints import rotate_key
        result = rotate_key(
            key_id="key-123",
            new_api_key="sk-new-key",
            db=mock_db
        )

        assert result["old_key_invalidated"] is True
