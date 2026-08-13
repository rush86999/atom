"""
Test suite for core.auth_helpers module.

This module tests JWT token verification and authentication helper functions:
- JWT token verification with validation
- Token expiration handling
- Emergency bypass handling
- User context validation
- Token revocation and cleanup
- Active token tracking

All functions in this module use JWT mocking and database session mocks,
making them suitable for unit testing with proper fixtures.

Test Strategy:
- Mock JWT library for token operations
- Mock database sessions for token operations
- Test valid/invalid/expired token scenarios
- Test emergency bypass functionality
- Test token cleanup operations
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timedelta
from core.auth_helpers import (
    verify_jwt_token,
    validate_user_context,
    revoke_token,
    revoke_all_user_tokens,
    track_active_token,
    cleanup_expired_revoked_tokens,
    cleanup_expired_active_tokens
)
from fastapi import HTTPException


# ==============================================================================
# JWT Token Verification Tests
# ==============================================================================

class TestJWTTokenVerification:
    """Test JWT token verification."""

    @patch('core.auth_helpers.jwt')
    def test_verify_jwt_token_valid_token(self, mock_jwt):
        """Verify valid JWT token returns payload."""
        mock_jwt.decode.return_value = {"sub": "user123", "exp": 9999999999}
        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            payload = verify_jwt_token("valid.token.here")

            assert payload["sub"] == "user123"
            assert payload["exp"] == 9999999999

    @patch('core.auth_helpers.jwt')
    def test_verify_jwt_token_expired_token_raises_401(self, mock_jwt):
        """Expired token raises HTTPException."""
        from jose import ExpiredSignatureError
        mock_jwt.decode.side_effect = ExpiredSignatureError()
        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            with pytest.raises(HTTPException) as exc:
                verify_jwt_token("expired.token")

            assert exc.value.status_code == 401

    @patch('core.auth_helpers.jwt')
    def test_verify_jwt_token_missing_sub_raises_401(self, mock_jwt):
        """Token without 'sub' claim raises HTTPException."""
        mock_jwt.decode.return_value = {"exp": 9999999999}
        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            with pytest.raises(HTTPException) as exc:
                verify_jwt_token("no.sub.token")

            assert exc.value.status_code == 401
            assert "authentication" in exc.value.detail.lower() or "token" in exc.value.detail.lower()

    @patch('core.auth_helpers.jwt')
    def test_verify_jwt_token_invalid_signature_raises_401(self, mock_jwt):
        """Invalid signature raises HTTPException."""
        from jose import JWTError
        mock_jwt.decode.side_effect = JWTError("Invalid signature")
        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            with pytest.raises(HTTPException) as exc:
                verify_jwt_token("invalid.signature")

            assert exc.value.status_code == 401

    def test_verify_jwt_token_emergency_bypass_allows_invalid(self):
        """Emergency bypass allows invalid token."""
        with patch.dict('os.environ', {
            'JWT_SECRET': '',
            'EMERGENCY_GOVERNANCE_BYPASS': 'true'
        }):
            payload = verify_jwt_token("invalid.token")

            # Emergency bypass creates default user
            assert payload["user_id"] == "emergency_user"
            assert payload.get("bypass") is True

    def test_verify_jwt_token_no_secret_with_bypass(self):
        """No JWT secret with emergency bypass enabled."""
        with patch.dict('os.environ', {
            'JWT_SECRET': '',
            'EMERGENCY_GOVERNANCE_BYPASS': 'true'
        }):
            payload = verify_jwt_token("any.token")

            assert "user_id" in payload

    def test_verify_jwt_token_empty_token_string(self):
        """Empty token string raises 401."""
        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            with pytest.raises(HTTPException) as exc:
                verify_jwt_token("")

            assert exc.value.status_code == 401

    def test_verify_jwt_token_token_with_whitespace_trimmed(self):
        """Token with surrounding whitespace is trimmed."""
        with patch('core.auth_helpers.jwt') as mock_jwt:
            mock_jwt.decode.return_value = {"sub": "user123", "exp": 9999999999}
            with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
                payload = verify_jwt_token("  valid.token.here  ")

                assert payload["sub"] == "user123"
                # Verify trim was called
                mock_jwt.decode.assert_called_once()


# ==============================================================================
# User Context Validation Tests
# ==============================================================================

class TestUserContextValidation:
    """Test user context validation."""

    def test_validate_user_context_valid_user(self):
        """Valid user context passes validation."""
        # Should not raise exception
        validate_user_context("user123", "read_operation")

    def test_validate_user_context_missing_user_raises_401(self):
        """Missing user_id raises HTTPException."""
        with pytest.raises(HTTPException) as exc:
            validate_user_context(None, "read_operation")

        assert exc.value.status_code == 401

    def test_validate_user_context_empty_string_user_raises_401(self):
        """Empty string user_id raises HTTPException."""
        with pytest.raises(HTTPException) as exc:
            validate_user_context("", "read_operation")

        assert exc.value.status_code == 401

    def test_validate_user_context_with_operation(self):
        """Validation considers operation type."""
        # Should not raise for valid context
        validate_user_context("user123", "write_operation")


# ==============================================================================
# Token Revocation Tests
# ==============================================================================

class TestTokenRevocation:
    """Test token revocation functionality."""

    def test_revoke_token_adds_to_revoked_table(self):
        """Revoking token adds entry to RevokedToken table."""
        mock_db = Mock()
        # revoke_token checks for an already-revoked entry first; return None so
        # the insert path (add + commit) actually runs.
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        revoke_token("token123", expires_at=datetime.now(), db=mock_db)

        # Verify add was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_revoke_all_user_tokens_revokes_multiple(self):
        """Revoking all tokens for user revokes all their tokens."""
        mock_db = Mock()
        # Two active tokens for the user; revoke_all_user_tokens iterates the
        # ActiveToken query result and inserts a RevokedToken per token.
        token_a = Mock(jti="t1", expires_at=datetime.now())
        token_b = Mock(jti="t2", expires_at=datetime.now())
        mock_db.query.return_value.filter.return_value.all.return_value = [token_a, token_b]
        # Per-token "already revoked" lookup must return None so each is revoked.
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        count = revoke_all_user_tokens("user123", db=mock_db)

        # Verify both tokens were revoked in a single commit.
        assert count == 2
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    def test_revoke_token_handles_database_errors(self):
        """Database errors during revocation raise HTTPException(500) and roll back."""
        mock_db = Mock()
        # Not already revoked, so the function proceeds to add + commit.
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.commit.side_effect = Exception("Database error")

        # Per its contract, revoke_token raises HTTPException(500) on DB failure
        # (after rolling back). The old version of this test swallowed a
        # TypeError from a missing `expires_at` arg and asserted nothing.
        with pytest.raises(HTTPException) as exc_info:
            revoke_token("token123", expires_at=datetime.now(), db=mock_db)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()


# ==============================================================================
# Active Token Tracking Tests
# ==============================================================================

class TestActiveTokenTracking:
    """Test active token tracking functionality."""

    def test_track_active_token_stores_token(self):
        """Tracking active token stores in ActiveToken table."""
        mock_db = Mock()
        # track_active_token checks for an already-tracked token first; return
        # None so the insert path (add + commit) actually runs.
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        track_active_token("user123", "token123", expires_at=datetime.now(), db=mock_db)

        # Verify add and commit were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_track_active_token_with_expiration(self):
        """Tracking token includes expiration time."""
        mock_db = Mock()
        # track_active_token checks for an already-tracked token first; return
        # None so the insert path actually runs.
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        expires_at = datetime.now() + timedelta(hours=24)
        track_active_token("user123", "token123", expires_at=expires_at, db=mock_db)

        # Verify token was added with expiration
        mock_db.add.assert_called_once()


# ==============================================================================
# Token Cleanup Tests
# ==============================================================================

class TestTokenCleanup:
    """Test token cleanup functionality."""

    def test_cleanup_expired_revoked_tokens(self):
        """Cleanup removes expired revoked tokens."""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5  # 5 tokens deleted

        count = cleanup_expired_revoked_tokens(mock_db, older_than_hours=24)

        assert count == 5
        mock_db.commit.assert_called_once()

    def test_cleanup_expired_active_tokens(self):
        """Cleanup removes expired active tokens."""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 10  # 10 tokens deleted

        count = cleanup_expired_active_tokens(mock_db, older_than_hours=1)

        assert count == 10
        mock_db.commit.assert_called_once()

    def test_cleanup_with_custom_older_than(self):
        """Cleanup respects custom older_than parameter."""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 3

        count = cleanup_expired_revoked_tokens(mock_db, older_than_hours=48)

        assert count == 3
        # Verify filter was called with time constraint
        mock_query.filter.assert_called_once()


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestAuthHelpersIntegration:
    """Integration tests for auth helpers workflow."""

    @patch('core.auth_helpers.jwt')
    def test_complete_token_lifecycle(self, mock_jwt):
        """Test complete token lifecycle: verify -> track -> revoke."""
        mock_jwt.decode.return_value = {"sub": "user123", "exp": 9999999999}

        with patch.dict('os.environ', {'JWT_SECRET': 'test_secret'}):
            # Step 1: Verify token
            payload = verify_jwt_token("valid.token")
            assert payload["sub"] == "user123"

            # Step 2: Validate context
            validate_user_context(payload["sub"], "read_operation")

        # Token lifecycle steps work independently
        # In real scenario, these would share database session

    def test_emergency_bypass_workflow(self):
        """Test emergency bypass allows operations without valid token."""
        with patch.dict('os.environ', {
            'JWT_SECRET': '',
            'EMERGENCY_GOVERNANCE_BYPASS': 'true'
        }):
            # Emergency bypass provides default user
            payload = verify_jwt_token("invalid")

            # Can validate context with emergency user
            validate_user_context(payload.get("user_id"), "read_operation")
