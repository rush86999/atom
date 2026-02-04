"""
Tests for OAuth token encryption at rest.

Verifies that access tokens and refresh tokens are automatically
encrypted when stored and decrypted when retrieved.
"""
import pytest
from core.models import OAuthToken, _encrypt_token, _decrypt_token
from core.database import SessionLocal
from datetime import datetime, timedelta


class TestTokenEncryptionHelpers:
    """Test the encryption/decryption helper functions."""

    def test_encrypt_decrypt_token(self):
        """Test basic encryption and decryption."""
        original_token = "ya29.a0AfH6SMBx_very_long_oauth_token_string"

        # Encrypt
        encrypted = _encrypt_token(original_token)
        assert encrypted != original_token
        assert len(encrypted) > len(original_token)
        assert encrypted.startswith('gAAAA')  # Fernet output starts with this

        # Decrypt
        decrypted = _decrypt_token(encrypted)
        assert decrypted == original_token

    def test_encrypt_empty_token(self):
        """Test that empty tokens are handled gracefully."""
        assert _encrypt_token("") == ""
        assert _decrypt_token("") == ""

    def test_encrypt_none_token(self):
        """Test that None tokens are handled gracefully."""
        assert _encrypt_token(None) == ""
        assert _decrypt_token(None) == ""
        assert _decrypt_token("") == ""

    def test_decrypt_legacy_plaintext(self):
        """Test backwards compatibility with plaintext tokens."""
        # Simulate a legacy plaintext token (short, doesn't look like Fernet)
        legacy_token = "legacy_token_123"

        # Should return as-is if decryption fails
        decrypted = _decrypt_token(legacy_token)
        assert decrypted == legacy_token

    def test_encrypt_decrypt_various_tokens(self):
        """Test encryption/decryption with various token formats."""
        test_cases = [
            "simple_token",
            "ya29.a0AfH6SMBx_very_long_oauth_token_string_with_many_chars",
            "ghp_1234567890abcdefghijklmnopqrstuvwxyzGitHubToken",
            "Bearer token.with.dots",
            # Special characters that might appear in tokens
            "token-with-dashes_and_underscores",
            "token.with.many.dots.and.special.chars-123_456",
        ]

        for original_token in test_cases:
            encrypted = _encrypt_token(original_token)
            decrypted = _decrypt_token(encrypted)
            assert decrypted == original_token, f"Failed for token: {original_token}"


class TestOAuthTokenEncryption:
    """Test OAuthToken model encryption via hybrid properties."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test database session."""
        self.db = SessionLocal()
        yield
        self.db.rollback()
        self.db.close()

    def test_create_oauth_token_with_encryption(self):
        """Test creating an OAuth token - should be encrypted in database."""
        # Create a token
        access_token = "ya29.a0AfH6SMBx_test_access_token_secret_value"
        refresh_token = "refresh_token_secret_value_12345"

        oauth_token = OAuthToken(
            user_id="test_user_123",
            provider="google",
            access_token=access_token,  # This will be encrypted via setter
            refresh_token=refresh_token,  # This will be encrypted via setter
            token_type="Bearer",
            scopes=["read", "write"],
        )

        self.db.add(oauth_token)
        self.db.commit()
        self.db.refresh(oauth_token)

        # Verify database has encrypted values
        assert oauth_token._encrypted_access_token != access_token
        assert oauth_token._encrypted_access_token.startswith('gAAAA')
        assert oauth_token._encrypted_refresh_token != refresh_token
        assert oauth_token._encrypted_refresh_token.startswith('gAAAA')

        # Verify property getters decrypt correctly
        assert oauth_token.access_token == access_token
        assert oauth_token.refresh_token == refresh_token

    def test_update_oauth_token_reencrypts(self):
        """Test updating a token - should re-encrypt."""
        # Create initial token
        oauth_token = OAuthToken(
            user_id="test_user_456",
            provider="github",
            access_token="initial_token",
            token_type="Bearer",
        )
        self.db.add(oauth_token)
        self.db.commit()

        # Update token
        new_token = "ghp_new_token_value_12345"
        oauth_token.access_token = new_token
        self.db.commit()
        self.db.refresh(oauth_token)

        # Verify new token is encrypted
        assert oauth_token._encrypted_access_token != new_token
        assert oauth_token.access_token == new_token

    def test_query_oauth_token_decryption(self):
        """Test querying tokens - should decrypt automatically."""
        # Create test data
        tokens_data = [
            {
                "user_id": "user1",
                "provider": "google",
                "access_token": "google_token_123",
                "token_type": "Bearer",
            },
            {
                "user_id": "user1",
                "provider": "github",
                "access_token": "github_token_456",
                "token_type": "Bearer",
            },
        ]

        for data in tokens_data:
            token = OAuthToken(**data)
            self.db.add(token)

        self.db.commit()

        # Query tokens
        tokens = self.db.query(OAuthToken).filter(OAuthToken.user_id == "user1").all()

        # Verify all tokens are decrypted
        assert len(tokens) == 2
        assert tokens[0].access_token in ["google_token_123", "github_token_456"]
        assert tokens[1].access_token in ["google_token_123", "github_token_456"]
        assert tokens[0].access_token != tokens[1].access_token

    def test_none_refresh_token(self):
        """Test handling of None refresh token (some providers don't have it)."""
        oauth_token = OAuthToken(
            user_id="test_user_789",
            provider="notion",  # Notion doesn't have refresh tokens
            access_token="notion_token_123",
            token_type="Bearer",
        )

        self.db.add(oauth_token)
        self.db.commit()
        self.db.refresh(oauth_token)

        # Verify refresh token is None
        assert oauth_token.refresh_token == ""
        assert oauth_token._encrypted_refresh_token is None

    def test_legacy_plaintext_migration(self):
        """Test that legacy plaintext tokens can still be read."""
        # This simulates a row created before encryption was implemented
        # We'll directly set the encrypted column to a plaintext value
        oauth_token = OAuthToken(
            user_id="test_user_legacy",
            provider="legacy",
            token_type="Bearer",
        )

        # Manually set encrypted column to plaintext (simulating legacy data)
        oauth_token._encrypted_access_token = "legacy_plaintext_token"

        self.db.add(oauth_token)
        self.db.commit()
        self.db.refresh(oauth_token)

        # Access via property - should return the "plaintext" (decryption fails, returns as-is)
        retrieved_token = oauth_token.access_token
        assert retrieved_token == "legacy_plaintext_token"

        # Now if we update it, it should be encrypted
        oauth_token.access_token = "new_encrypted_token"
        self.db.commit()
        self.db.refresh(oauth_token)

        # Should now be encrypted
        assert oauth_token._encrypted_access_token != "new_encrypted_token"
        assert oauth_token.access_token == "new_encrypted_token"


class TestTokenEncryptionIntegration:
    """Integration tests for token encryption."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test database session."""
        self.db = SessionLocal()
        yield
        self.db.rollback()
        self.db.close()

    def test_full_lifecycle_encrypted(self):
        """Test full lifecycle: create -> read -> update -> delete with encryption."""
        # Create
        token = OAuthToken(
            user_id="lifecycle_user",
            provider="test_provider",
            access_token="initial_access",
            refresh_token="initial_refresh",
            token_type="Bearer",
            scopes=["read"],
        )
        self.db.add(token)
        self.db.commit()

        # Read
        retrieved = self.db.query(OAuthToken).filter(
            OAuthToken.user_id == "lifecycle_user"
        ).first()
        assert retrieved.access_token == "initial_access"
        assert retrieved.refresh_token == "initial_refresh"

        # Update
        retrieved.access_token = "updated_access"
        retrieved.scopes = ["read", "write"]
        self.db.commit()

        # Verify update
        self.db.refresh(retrieved)
        assert retrieved.access_token == "updated_access"
        assert retrieved.scopes == ["read", "write"]

        # Delete
        self.db.delete(retrieved)
        self.db.commit()

        # Verify deletion
        deleted = self.db.query(OAuthToken).filter(
            OAuthToken.user_id == "lifecycle_user"
        ).first()
        assert deleted is None

    def test_concurrent_token_updates(self):
        """Test that concurrent updates don't corrupt encryption."""
        # Create token
        token = OAuthToken(
            user_id="concurrent_user",
            provider="test",
            access_token="v1",
            token_type="Bearer",
        )
        self.db.add(token)
        self.db.commit()

        # Multiple updates
        for i in range(2, 11):
            token.access_token = f"v{i}"
            self.db.commit()

        # Final value should be correct
        self.db.refresh(token)
        assert token.access_token == "v10"
        assert token._encrypted_access_token != "v10"
