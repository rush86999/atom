"""
Tests for JWT Token Revocation Functionality

Tests the RevokedToken model and token revocation helpers.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.auth_helpers import (
    revoke_token,
    cleanup_expired_revoked_tokens,
)
from core.jwt_verifier import JWTVerifier
from core.models import RevokedToken


class TestRevokedTokenModel:
    """Test RevokedToken database model"""

    def test_create_revoked_token(self, db: Session):
        """Test creating a revoked token entry"""
        # Create a revoked token
        revoked = RevokedToken(
            jti="test-jti-123",
            expires_at=datetime.now() + timedelta(hours=24),
            user_id="test-user-123",
            revocation_reason="logout"
        )

        db.add(revoked)
        db.commit()

        # Verify it was saved
        retrieved = db.query(RevokedToken).filter_by(jti="test-jti-123").first()
        assert retrieved is not None
        assert retrieved.jti == "test-jti-123"
        assert retrieved.user_id == "test-user-123"
        assert retrieved.revocation_reason == "logout"
        assert retrieved.revoked_at is not None

    def test_unique_jti_constraint(self, db: Session):
        """Test that JTI must be unique"""
        # Create first token
        revoked1 = RevokedToken(
            jti="test-jti-unique",
            expires_at=datetime.now() + timedelta(hours=24),
            user_id="user-1"
        )
        db.add(revoked1)
        db.commit()

        # Try to create duplicate
        revoked2 = RevokedToken(
            jti="test-jti-unique",  # Same JTI
            expires_at=datetime.now() + timedelta(hours=24),
            user_id="user-2"
        )
        db.add(revoked2)

        with pytest.raises(Exception):  # IntegrityError
            db.commit()

    def test_query_by_user(self, db: Session):
        """Test querying revoked tokens by user"""
        # Add multiple tokens for same user
        for i in range(3):
            revoked = RevokedToken(
                jti=f"test-jti-{i}",
                expires_at=datetime.now() + timedelta(hours=24),
                user_id="test-user-multi"
            )
            db.add(revoked)
        db.commit()

        # Query
        results = db.query(RevokedToken).filter_by(user_id="test-user-multi").all()
        assert len(results) == 3


class TestRevokeToken:
    """Test revoke_token helper function"""

    def test_revoke_token_success(self, db: Session):
        """Test successfully revoking a token"""
        was_revoked = revoke_token(
            jti="test-revoke-123",
            expires_at=datetime.now() + timedelta(hours=24),
            db=db,
            user_id="user-123",
            revocation_reason="logout"
        )

        assert was_revoked is True

        # Verify in database
        revoked = db.query(RevokedToken).filter_by(jti="test-revoke-123").first()
        assert revoked is not None
        assert revoked.user_id == "user-123"
        assert revoked.revocation_reason == "logout"

    def test_revoke_already_revoked_token(self, db: Session):
        """Test revoking a token that's already revoked"""
        # First revocation
        revoke_token(
            jti="test-double-revoke",
            expires_at=datetime.now() + timedelta(hours=24),
            db=db,
            user_id="user-123"
        )

        # Second revocation
        was_revoked = revoke_token(
            jti="test-double-revoke",
            expires_at=datetime.now() + timedelta(hours=24),
            db=db,
            user_id="user-123"
        )

        assert was_revoked is False  # Already revoked

    def test_revoke_token_with_optional_fields(self, db: Session):
        """Test revoking token with optional fields"""
        was_revoked = revoke_token(
            jti="test-optional-123",
            expires_at=datetime.now() + timedelta(hours=24),
            db=db,
            user_id="user-456",
            revocation_reason="security_breach"
        )

        assert was_revoked is True

        revoked = db.query(RevokedToken).filter_by(jti="test-optional-123").first()
        assert revoked.revocation_reason == "security_breach"


class TestCleanupExpiredTokens:
    """Test cleanup_expired_revoked_tokens helper"""

    def test_cleanup_old_tokens(self, db: Session):
        """Test cleaning up expired tokens"""
        # Add expired token (old)
        old_token = RevokedToken(
            jti="old-token",
            expires_at=datetime.now() - timedelta(hours=48),  # 2 days ago
            user_id="user-123"
        )
        db.add(old_token)

        # Add recent token (not old enough)
        recent_token = RevokedToken(
            jti="recent-token",
            expires_at=datetime.now() - timedelta(hours=12),  # 12 hours ago
            user_id="user-123"
        )
        db.add(recent_token)

        # Add active token (not expired)
        active_token = RevokedToken(
            jti="active-token",
            expires_at=datetime.now() + timedelta(hours=24),
            user_id="user-123"
        )
        db.add(active_token)

        db.commit()

        # Cleanup tokens older than 24 hours
        deleted_count = cleanup_expired_revoked_tokens(db, older_than_hours=24)

        assert deleted_count == 1  # Only old_token deleted

        # Verify
        assert db.query(RevokedToken).filter_by(jti="old-token").first() is None
        assert db.query(RevokedToken).filter_by(jti="recent-token").first() is not None
        assert db.query(RevokedToken).filter_by(jti="active-token").first() is not None

    def test_cleanup_all_tokens(self, db: Session):
        """Test cleaning up all expired tokens"""
        # Add multiple expired tokens
        for i in range(5):
            token = RevokedToken(
                jti=f"expired-{i}",
                expires_at=datetime.now() - timedelta(days=7),
                user_id="user-123"
            )
            db.add(token)

        db.commit()

        # Cleanup
        deleted = cleanup_expired_revoked_tokens(db, older_than_hours=1)
        assert deleted == 5

        # All gone
        remaining = db.query(RevokedToken).filter(
            RevokedToken.jti.like("expired-%")
        ).count()
        assert remaining == 0


class TestJWTVerifierRevocation:
    """Test JWTVerifier._is_token_revoked method"""

    def test_verify_non_revoked_token(self, db: Session):
        """Test that non-revoked tokens pass validation"""
        verifier = JWTVerifier(secret_key="test-secret")

        payload = {
            "sub": "user-123",
            "jti": "never-revoked-jti",
            "exp": int((datetime.now() + timedelta(hours=1)).timestamp())
        }

        # Token should not be revoked
        is_revoked = verifier._is_token_revoked(payload, db)
        assert is_revoked is False

    def test_verify_revoked_token(self, db: Session):
        """Test that revoked tokens are detected"""
        verifier = JWTVerifier(secret_key="test-secret")

        # First, revoke a token
        revoke_token(
            jti="revoked-jti-456",
            expires_at=datetime.now() + timedelta(hours=1),
            db=db,
            user_id="user-456",
            revocation_reason="logout"
        )

        # Now check if it's revoked
        payload = {
            "sub": "user-456",
            "jti": "revoked-jti-456",
            "exp": int((datetime.now() + timedelta(hours=1)).timestamp())
        }

        is_revoked = verifier._is_token_revoked(payload, db)
        assert is_revoked is True

    def test_verify_token_without_db(self, db: Session):
        """Test that verification works without db session (graceful degradation)"""
        verifier = JWTVerifier(secret_key="test-secret")

        payload = {
            "sub": "user-789",
            "jti": "no-db-jti",
            "exp": int((datetime.now() + timedelta(hours=1)).timestamp())
        }

        # Without db, should return False (not revoked)
        is_revoked = verifier._is_token_revoked(payload, db=None)
        assert is_revoked is False

    def test_verify_token_without_jti(self, db: Session):
        """Test that tokens without JTI cannot be checked for revocation"""
        verifier = JWTVerifier(secret_key="test-secret")

        payload = {
            "sub": "user-999",
            # No "jti" field
            "exp": int((datetime.now() + timedelta(hours=1)).timestamp())
        }

        # Should return False (cannot check revocation)
        is_revoked = verifier._is_token_revoked(payload, db)
        assert is_revoked is False


class TestCreateTokenWithJTI:
    """Test JWTVerifier.create_token includes JTI"""

    def test_create_token_has_jti(self):
        """Test that created tokens include JTI claim"""
        verifier = JWTVerifier(secret_key="test-secret")

        token = verifier.create_token(
            subject="user-123",
            expires_delta=timedelta(hours=1)
        )

        # Decode and check for JTI
        import jwt
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])

        assert "jti" in payload
        assert payload["sub"] == "user-123"
        assert len(payload["jti"]) > 0  # Should have a UUID

    def test_create_token_with_custom_jti(self):
        """Test creating token with custom JTI"""
        verifier = JWTVerifier(secret_key="test-secret")

        custom_jti = "my-custom-jti-123"
        token = verifier.create_token(
            subject="user-456",
            expires_delta=timedelta(hours=1),
            jti=custom_jti
        )

        # Decode and verify JTI
        import jwt
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])

        assert payload["jti"] == custom_jti
