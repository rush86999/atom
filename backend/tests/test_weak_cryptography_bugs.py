"""
Test suite for Weak Cryptography hardening verification.

These suites were originally RED-phase tests that asserted the OLD insecure
behavior (MD5/SHA1 usage). The R-round security hardening replaced every
MD5 usage with SHA-256, so the tests are aligned to the CURRENT (fixed)
implementations: MD5 must be absent and SHA-256 present at every site.

Sites (all verified SHA-256 today):
1. core/communication/adapters/intercom.py — SHA256 HMAC (SHA1 kept only for
   legacy verification, with a deprecation note)
2. core/byok_cache_preseeding.py:488 — SHA256 for cache key generation
3. core/llm/compression/session_dedup.py:110 — SHA256 for content dedup
   (formerly core/unified_message_processor.py, which no longer exists)
4. core/integration_data_mapper.py:246 — SHA256 for ID generation
5. core/canvas_presentation_summary.py:86 — SHA256 for cache invalidation
"""

import pytest


class TestWeakCryptographyVulnerabilities:
    """
    Test suite verifying weak-cryptography vulnerabilities are CLOSED.

    The former bugs: Weak hash algorithms (MD5, SHA1) used for security-sensitive
    and non-security purposes. MD5 and SHA1 are deprecated due to collision
    vulnerabilities and have been replaced with SHA256 or stronger.
    """

    def test_intercom_webhook_uses_sha1_hmac(self):
        """
        Test that Intercom webhook verification supports SHA256 (and SHA1 only
        for legacy webhooks, flagged deprecated).

        FIXED: Line 51 previously used hashlib.sha1 for HMAC signature
        verification. SHA256 is now the supported algorithm.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/communication/adapters/intercom.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is used for HMAC
        assert 'hashlib.sha256' in source, \
            "Fix confirmed: SHA256 is used for HMAC signature verification"

        # SHA1 may remain only for backward compatibility, never as the default
        if 'hashlib.sha1' in source:
            assert 'deprecated' in source.lower() or 'security_note' in source.lower(), \
                "Fix confirmed: any remaining SHA1 usage is flagged deprecated"

    def test_byok_cache_uses_md5(self):
        """
        Test that BYOK cache preseeding no longer uses MD5 (weak).

        FIXED: Line 487 previously used hashlib.md5 for prompt hashing.
        MD5 is deprecated and has been replaced with SHA256.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/byok_cache_preseeding.py', 'r') as f:
            source = f.read()

        # Verify the fix - MD5 is gone, SHA256 is used
        assert 'hashlib.md5' not in source, \
            "Fix confirmed: MD5 is no longer used for prompt hashing"
        assert 'hashlib.sha256' in source, \
            "Fix confirmed: SHA256 is used for prompt hashing"

    def test_unified_message_processor_uses_md5(self):
        """
        Test that content deduplication no longer uses MD5 (weak).

        FIXED: Line 391 previously used hashlib.md5 for content deduplication.
        The module was consolidated into core/llm/compression/session_dedup.py,
        which uses SHA256 for exact-match chunk hashing.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/llm/compression/session_dedup.py', 'r') as f:
            source = f.read()

        # Verify the fix - MD5 is gone, SHA256 is used
        assert 'hashlib.md5' not in source, \
            "Fix confirmed: MD5 is no longer used for content deduplication hashing"
        assert 'hashlib.sha256' in source, \
            "Fix confirmed: SHA256 is used for content deduplication hashing"

    def test_integration_data_mapper_uses_md5(self):
        """
        Test that integration data mapper no longer uses MD5 (weak).

        FIXED: Line 244 previously used hashlib.md5 for ID generation.
        SHA256 is now used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/integration_data_mapper.py', 'r') as f:
            source = f.read()

        # Verify the fix - MD5 is gone, SHA256 is used
        assert 'hashlib.md5' not in source, \
            "Fix confirmed: MD5 is no longer used for ID generation"
        assert 'hashlib.sha256' in source, \
            "Fix confirmed: SHA256 is used for ID generation"

    def test_canvas_presentation_summary_uses_md5(self):
        """
        Test that canvas presentation summary no longer uses MD5 (weak).

        FIXED: Line 85 previously used hashlib.md5 for cache invalidation.
        SHA256 is now used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/canvas_presentation_summary.py', 'r') as f:
            source = f.read()

        # Verify the fix - MD5 is gone, SHA256 is used
        assert 'hashlib.md5' not in source, \
            "Fix confirmed: MD5 is no longer used for cache invalidation hashing"
        assert 'hashlib.sha256' in source, \
            "Fix confirmed: SHA256 is used for cache invalidation hashing"

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
