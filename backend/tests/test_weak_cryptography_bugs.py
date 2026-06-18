"""
Test suite for Weak Cryptography vulnerabilities.

RED PHASE: These tests expose weak cryptography bugs.

The bugs:
1. core/communication/adapters/intercom.py:51 - SHA1 for HMAC webhook signature
2. core/byok_cache_preseeding.py:487 - MD5 for cache key generation
3. core/unified_message_processor.py:391 - MD5 for content deduplication
4. core/integration_data_mapper.py:244 - MD5 for ID generation
5. core/canvas_presentation_summary.py:85 - MD5 for cache invalidation
"""

import pytest


class TestWeakCryptographyVulnerabilities:
    """
    Test suite revealing weak cryptography vulnerabilities.

    The bug: Weak hash algorithms (MD5, SHA1) are used for security-sensitive
    and non-security purposes. MD5 and SHA1 are deprecated due to collision
    vulnerabilities and should be replaced with SHA256 or stronger.
    """

    def test_intercom_webhook_uses_sha1_hmac(self):
        """
        Test that Intercom webhook verification uses SHA1 (weak).

        BUG: Line 51 - Uses hashlib.sha1 for HMAC signature verification.
        SHA1 is deprecated and vulnerable to collision attacks.
        Should use SHA256.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/communication/adapters/intercom.py', 'r') as f:
            source = f.read()

        # Verify the bug - SHA1 is used for HMAC
        assert 'digestmod=hashlib.sha1' in source or 'hashlib.sha1' in source, \
            "Bug confirmed: SHA1 is used for HMAC signature verification"

        # Verify SHA256 is NOT used
        assert 'hashlib.sha256' not in source or 'digestmod=hashlib.sha256' not in source, \
            "Bug confirmed: SHA256 is not used for HMAC (should be upgraded from SHA1)"

    def test_byok_cache_uses_md5(self):
        """
        Test that BYOK cache preseeding uses MD5 (weak).

        BUG: Line 487 - Uses hashlib.md5 for prompt hashing.
        MD5 is deprecated and should be replaced with SHA256.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/byok_cache_preseeding.py', 'r') as f:
            source = f.read()

        # Verify the bug - MD5 is used
        assert 'hashlib.md5' in source, \
            "Bug confirmed: MD5 is used for prompt hashing"

    def test_unified_message_processor_uses_md5(self):
        """
        Test that unified message processor uses MD5 (weak).

        BUG: Line 391 - Uses hashlib.md5 for content deduplication.
        Should use SHA256 for better security.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/unified_message_processor.py', 'r') as f:
            source = f.read()

        # Verify the bug - MD5 is used for content hashing
        assert 'hashlib.md5' in source, \
            "Bug confirmed: MD5 is used for content deduplication hashing"

    def test_integration_data_mapper_uses_md5(self):
        """
        Test that integration data mapper uses MD5 (weak).

        BUG: Line 244 - Uses hashlib.md5 for ID generation.
        Should use SHA256 for better security.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/integration_data_mapper.py', 'r') as f:
            source = f.read()

        # Verify the bug - MD5 is used for ID generation
        assert 'hashlib.md5' in source, \
            "Bug confirmed: MD5 is used for ID generation"

    def test_canvas_presentation_summary_uses_md5(self):
        """
        Test that canvas presentation summary uses MD5 (weak).

        BUG: Line 85 - Uses hashlib.md5 for cache invalidation.
        Should use SHA256 for better security.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/canvas_presentation_summary.py', 'r') as f:
            source = f.read()

        # Verify the bug - MD5 is used for cache hashing
        assert 'hashlib.md5' in source, \
            "Bug confirmed: MD5 is used for cache invalidation hashing"

    def test_password_hashing_uses_bcrypt(self):
        """
        Test that password hashing uses bcrypt (secure).

        SAFE: core/auth.py uses bcrypt for password hashing,
        which is the industry standard and secure.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/auth.py', 'r') as f:
            source = f.read()

        # Verify bcrypt is used for passwords
        assert 'bcrypt' in source and 'hashpw' in source, \
            "Safe: Bcrypt is used for password hashing"

        # Verify MD5 is NOT used for passwords
        assert 'hashlib.md5' not in source, \
            "Safe: MD5 is not used for password hashing"

    def test_token_encryption_uses_fernet(self):
        """
        Test that token encryption uses Fernet (secure).

        SAFE: core/privsec/token_encryption.py uses Fernet
        (AES-128-CBC + HMAC) for token encryption, which is secure.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/privsec/token_encryption.py', 'r') as f:
            source = f.read()

        # Verify Fernet is used for encryption
        assert 'Fernet' in source and 'cryptography.fernet' in source, \
            "Safe: Fernet (AES-128-CBC + HMAC) is used for token encryption"

        # Verify SHA256 is used for token hashing
        assert 'hashlib.sha256' in source, \
            "Safe: SHA256 is used for token hashing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
