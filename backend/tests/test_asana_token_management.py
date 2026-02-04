#!/usr/bin/env python3
"""
Tests for Asana Token Management
Tests the proper token retrieval and storage for Asana integration
"""

import os
import tempfile
import pytest
from consolidated.integrations.asana_routes import (
    delete_asana_token,
    get_access_token,
    save_asana_token,
)
from fastapi import HTTPException

from core.token_storage import TokenStorage

# Sample token data
SAMPLE_TOKEN_DATA = {
    "access_token": "1/12045927654321abcdef123456789",
    "refresh_token": "1/987654321fedcba54321098765432",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "default"
}


@pytest.fixture
def temp_token_file(monkeypatch):
    """Create temporary token file for testing"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
    temp_file.close()

    # Patch TokenStorage to use temp file
    from consolidated.integrations import asana_routes
    original_storage = asana_routes.TokenStorage

    def mock_storage(cls, storage_file=None):
        return original_storage(storage_file=temp_file.name)

    monkeypatch.setattr(asana_routes, "TokenStorage", mock_storage)

    yield temp_file.name

    # Cleanup
    try:
        os.unlink(temp_file.name)
    except:
        pass


class TestTokenRetrieval:
    """Tests for token retrieval"""

    @pytest.mark.asyncio
    async def test_get_token_success(self, temp_token_file):
        """Test successful token retrieval"""
        # First save a token
        save_asana_token("user123", SAMPLE_TOKEN_DATA)

        # Then retrieve it
        token = await get_access_token(user_id="user123")

        assert token == SAMPLE_TOKEN_DATA["access_token"]

    @pytest.mark.asyncio
    async def test_get_token_not_found(self, temp_token_file):
        """Test token retrieval when no token exists"""
        with pytest.raises(HTTPException) as exc_info:
            await get_access_token(user_id="nonexistent_user")

        assert exc_info.value.status_code == 401
        assert "No Asana token found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_token_expired(self, temp_token_file):
        """Test token retrieval when token is expired"""
        # Save an expired token
        expired_token = SAMPLE_TOKEN_DATA.copy()
        from datetime import datetime, timedelta
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        expired_token["expires_at"] = expired_time

        save_asana_token("user456", expired_token)

        # Try to retrieve expired token
        with pytest.raises(HTTPException) as exc_info:
            await get_access_token(user_id="user456")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_token_invalid_data(self, temp_token_file):
        """Test token retrieval when token data is invalid"""
        # Save token without access_token
        save_asana_token("user789", {"refresh_token": "some_token"})

        with pytest.raises(HTTPException) as exc_info:
            await get_access_token(user_id="user789")

        assert exc_info.value.status_code == 401
        assert "missing access_token" in exc_info.value.detail


class TestTokenStorage:
    """Tests for token storage"""

    def test_save_token_success(self, temp_token_file):
        """Test successful token storage"""
        result = save_asana_token("user001", SAMPLE_TOKEN_DATA)

        assert result is True

        # Verify token was saved
        storage = TokenStorage(storage_file=temp_token_file)
        token = storage.get_token("asana_user001")
        assert token is not None
        assert token["access_token"] == SAMPLE_TOKEN_DATA["access_token"]

    def test_save_token_multiple_users(self, temp_token_file):
        """Test saving tokens for multiple users"""
        save_asana_token("user001", SAMPLE_TOKEN_DATA)
        save_asana_token("user002", {
            "access_token": "different_token",
            "refresh_token": "different_refresh",
            "token_type": "Bearer"
        })

        storage = TokenStorage(storage_file=temp_token_file)

        token1 = storage.get_token("asana_user001")
        token2 = storage.get_token("asana_user002")

        assert token1["access_token"] == SAMPLE_TOKEN_DATA["access_token"]
        assert token2["access_token"] == "different_token"

    def test_save_token_updates_existing(self, temp_token_file):
        """Test that saving a token updates existing token"""
        save_asana_token("user003", SAMPLE_TOKEN_DATA)

        # Update with new token
        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token"
        }
        save_asana_token("user003", new_token)

        storage = TokenStorage(storage_file=temp_token_file)
        token = storage.get_token("asana_user003")

        assert token["access_token"] == "new_access_token"


class TestTokenDeletion:
    """Tests for token deletion"""

    def test_delete_token_success(self, temp_token_file):
        """Test successful token deletion"""
        # Save token first
        save_asana_token("user004", SAMPLE_TOKEN_DATA)

        # Verify it exists
        storage = TokenStorage(storage_file=temp_token_file)
        assert storage.get_token("asana_user004") is not None

        # Delete it
        result = delete_asana_token("user004")
        assert result is True

        # Verify it's gone (or empty)
        token = storage.get_token("asana_user004")
        assert token is None or token == {}

    def test_delete_nonexistent_token(self, temp_token_file):
        """Test deleting a token that doesn't exist"""
        result = delete_asana_token("nonexistent_user")
        # Should still return True (idempotent)
        assert result is True


class TestTokenExpiry:
    """Tests for token expiry handling"""

    def test_token_expiry_calculation(self, temp_token_file):
        """Test that token expiry is calculated correctly"""
        from datetime import datetime, timedelta

        save_asana_token("user005", SAMPLE_TOKEN_DATA)

        storage = TokenStorage(storage_file=temp_token_file)
        token = storage.get_token("asana_user005")

        # Check that expires_at was set
        assert "expires_at" in token

        # Parse expiry time
        expires_at = datetime.fromisoformat(token["expires_at"])

        # Should be approximately 1 hour from now (within 5 seconds)
        expected_expiry = datetime.now() + timedelta(seconds=3600)
        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_token_expiry_with_custom_expires_in(self, temp_token_file):
        """Test expiry with custom expires_in value"""
        from datetime import datetime, timedelta

        custom_token = SAMPLE_TOKEN_DATA.copy()
        custom_token["expires_in"] = 7200  # 2 hours

        save_asana_token("user006", custom_token)

        storage = TokenStorage(storage_file=temp_token_file)
        token = storage.get_token("asana_user006")

        expires_at = datetime.fromisoformat(token["expires_at"])
        expected_expiry = datetime.now() + timedelta(seconds=7200)

        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
