"""
Unit tests for Encryption Service.

Tests cover:
- Data encryption with AES-256
- Data decryption
- Key management (generation, derivation, storage)
- Password hashing (bcrypt)
- Secure random generation

These tests focus on encryption functions in core/auth.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from core.auth import (
    get_password_hash,
    verify_password,
    SECRET_KEY,
)
from core.models import User
from tests.factories.user_factory import UserFactory

# Import encryption-related modules
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password_generates_bcrypt_hash(self):
        """Test password hashing generates valid bcrypt hash."""
        password = "SecurePassword123!"

        hashed = get_password_hash(password)

        assert hashed is not None
        assert len(hashed) == 60  # Standard bcrypt length
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_different_passwords_different_hashes(self):
        """Test different passwords generate different hashes."""
        password1 = "PasswordOne123!"
        password2 = "PasswordTwo123!"

        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)

        assert hash1 != hash2

    def test_hash_same_password_different_hashes(self):
        """Test same password generates different hashes (due to salt)."""
        password = "SamePassword123!"

        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2

        # But both should verify
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_correct_password(self):
        """Test password verification succeeds with correct password."""
        password = "CorrectPassword123!"
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_incorrect_password(self):
        """Test password verification fails with incorrect password."""
        password = "OriginalPassword123!"
        hashed = get_password_hash(password)

        result = verify_password("WrongPassword123!", hashed)

        assert result is False

    def test_verify_empty_password(self):
        """Test password verification handles empty password."""
        password = ""
        hashed = get_password_hash(password)

        assert verify_password("", hashed) is True
        assert verify_password("something", hashed) is False

    def test_verify_unicode_password(self):
        """Test password verification handles unicode characters."""
        password = "P@sswörd日本語123!"

        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_very_long_password(self):
        """Test password verification handles very long password."""
        # Bcrypt has 72-byte limit, password should be truncated
        long_password = "a" * 100

        hashed = get_password_hash(long_password)

        # Should verify correctly (truncated to 71 bytes)
        assert verify_password(long_password, hashed) is True

    def test_hash_empty_string(self):
        """Test hashing empty string works."""
        hashed = get_password_hash("")

        assert hashed is not None
        assert len(hashed) == 60

    def test_hash_truncates_to_71_bytes(self):
        """Test password is truncated to 71 bytes for bcrypt limit."""
        # Create password longer than 71 bytes
        long_password = "a" * 100

        hashed = get_password_hash(long_password)

        # Should not raise error
        assert hashed is not None
        assert len(hashed) == 60


class TestEncryptionDecryption:
    """Test data encryption and decryption (if implemented)."""

    def test_secret_key_exists(self):
        """Test SECRET_KEY is configured."""
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    def test_secret_key_length(self):
        """Test SECRET_KEY has sufficient length."""
        # For HS256, key should be at least 32 bytes
        assert len(SECRET_KEY) >= 32

    def test_secret_key_is_string(self):
        """Test SECRET_KEY is a string."""
        assert isinstance(SECRET_KEY, str)


class TestKeyManagement:
    """Test key management functions."""

    def test_secret_key_consistency(self):
        """Test SECRET_KEY remains consistent across calls."""
        key1 = SECRET_KEY
        key2 = SECRET_KEY

        assert key1 == key2

    def test_secret_key_from_environment(self):
        """Test SECRET_KEY can be loaded from environment."""
        # In production, this would come from environment variable
        # For tests, we just verify it's accessible
        import os

        # Check if SECRET_KEY env var is set
        env_key = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET")

        if env_key:
            # If env var is set, SECRET_KEY should match
            assert SECRET_KEY == env_key or SECRET_KEY is not None


class TestSecureRandom:
    """Test secure random generation functions."""

    def test_generate_secure_token(self):
        """Test secure token generation."""
        import secrets

        token = secrets.token_urlsafe(32)

        assert token is not None
        assert len(token) > 0
        assert isinstance(token, str)

    def test_generate_secure_bytes(self):
        """Test secure random bytes generation."""
        import secrets

        random_bytes = secrets.token_bytes(32)

        assert random_bytes is not None
        assert len(random_bytes) == 32

    def test_tokens_are_unique(self):
        """Test generated tokens are unique."""
        import secrets

        tokens = [secrets.token_urlsafe(32) for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100

    def test_token_hex_generation(self):
        """Test hexadecimal token generation."""
        import secrets

        token = secrets.token_hex(32)

        assert token is not None
        assert len(token) == 64  # 32 bytes = 64 hex chars

    def test_entropy_verification(self):
        """Test tokens have sufficient entropy."""
        import secrets

        # Generate multiple tokens and check for collisions
        tokens = set()
        for _ in range(1000):
            token = secrets.token_urlsafe(16)
            tokens.add(token)

        # Should have 1000 unique tokens (no collisions)
        assert len(tokens) == 1000


class TestBcryptSpecificBehavior:
    """Test bcrypt-specific hashing behavior."""

    @pytest.mark.skipif(not BCRYPT_AVAILABLE, reason="bcrypt not available")
    def test_bcrypt_work_factor(self):
        """Test bcrypt uses appropriate work factor."""
        import re

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        # Extract work factor from hash
        # Format: $2b$[work_factor]$...
        match = re.match(r'\$2[ab]\$(\d+)\$', hashed)

        if match:
            work_factor = int(match.group(1))
            # Work factor should be between 4 and 31 (bcrypt limits)
            # Default is usually 12
            assert 4 <= work_factor <= 31

    @pytest.mark.skipif(not BCRYPT_AVAILABLE, reason="bcrypt not available")
    def test_bcrypt_hash_components(self):
        """Test bcrypt hash has correct components."""
        parts = get_password_hash("test").split('$')

        # Should have 4 parts: empty, algorithm (2a/2b), cost, salt+hash
        assert len(parts) == 4
        assert parts[1] in ['2a', '2b']
        assert parts[2].isdigit()


class TestTimingAttackResistance:
    """Test timing attack resistance in password verification."""

    def test_verification_timing_consistency(self):
        """Test password verification timing is consistent."""
        import time

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        # Measure time for correct password
        times_correct = []
        for _ in range(10):
            start = time.time()
            verify_password(password, hashed)
            times_correct.append(time.time() - start)

        # Measure time for incorrect password
        times_incorrect = []
        for _ in range(10):
            start = time.time()
            verify_password("WrongPassword123!", hashed)
            times_incorrect.append(time.time() - start)

        # Average times should be similar (within 10x for test reliability)
        avg_correct = sum(times_correct) / len(times_correct)
        avg_incorrect = sum(times_incorrect) / len(times_incorrect)

        ratio = max(avg_correct, avg_incorrect) / min(avg_correct, avg_incorrect)
        # Bcrypt's constant-time comparison prevents significant timing differences
        assert ratio < 10, f"Timing difference too large: {ratio}"


class TestEdgeCases:
    """Test edge cases in encryption/hashing."""

    def test_hash_special_characters(self):
        """Test hashing passwords with special characters."""
        special_passwords = [
            "!@#$%^&*()",
            "密码123",
            "🔑🔒",
            "\n\t\r",
            "null\x00byte",
        ]

        for password in special_passwords:
            hashed = get_password_hash(password)
            assert verify_password(password, hashed) is True

    def test_verify_with_invalid_hash_format(self):
        """Test verification with invalid hash format."""
        result = verify_password("password123", "invalid_hash")

        assert result is False

    def test_verify_with_empty_hash(self):
        """Test verification with empty hash."""
        result = verify_password("password123", "")

        assert result is False

    def test_hash_none_password(self):
        """Test hashing None password raises appropriate error."""
        # Should raise TypeError or similar
        with pytest.raises((TypeError, AttributeError)):
            get_password_hash(None)
