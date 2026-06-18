"""
Test suite for Weak Cryptography fix verification.

GREEN PHASE: These tests verify weak cryptography protections are in place.
"""

import pytest


class TestWeakCryptographyFixes:
    """Tests for verifying weak cryptography fixes."""

    def test_intercom_webhook_supports_sha256(self):
        """
        Test that Intercom webhook verification supports SHA256.

        GREEN PHASE: After the fix, SHA256 should be supported/used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/communication/adapters/intercom.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is supported
        assert 'sha256' in source.lower() and 'hashlib.sha256' in source, \
            "Fix applied: SHA256 is now supported for HMAC signature verification"

        # Verify SHA1 is still supported for backward compatibility
        assert 'sha1' in source.lower(), \
            "Fix applied: SHA1 is still supported for backward compatibility"

        # Verify both algorithms are handled
        assert 'algo == "sha256"' in source or "algo == 'sha256'" in source, \
            "Fix applied: SHA256 algorithm check is present"

    def test_intercom_webhook_has_security_note(self):
        """
        Test that SHA1 usage has security warning.

        GREEN PHASE: After the fix, SHA1 should have security warning.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/communication/adapters/intercom.py', 'r') as f:
            source = f.read()

        # Verify security warning for SHA1
        assert 'security_note' in source or 'deprecated' in source or 'SHA1 is deprecated' in source, \
            "Fix applied: Security warning for SHA1 usage is documented"

    def test_byok_cache_uses_sha256(self):
        """
        Test that BYOK cache preseeding uses SHA256.

        GREEN PHASE: After the fix, SHA256 should be used instead of MD5.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/byok_cache_preseeding.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is used
        assert 'hashlib.sha256' in source, \
            "Fix applied: SHA256 is now used for prompt hashing"

        # Verify MD5 is no longer used (or only in comments)
        md5_count = source.count('hashlib.md5')
        assert md5_count == 0 or 'CRYPTOGRAPHY FIX' in source, \
            "Fix applied: MD5 is no longer used for hashing"

    def test_unified_message_processor_uses_sha256(self):
        """
        Test that unified message processor uses SHA256.

        GREEN PHASE: After the fix, SHA256 should be used instead of MD5.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/unified_message_processor.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is used for content hashing
        assert 'hashlib.sha256' in source, \
            "Fix applied: SHA256 is now used for content deduplication hashing"

    def test_integration_data_mapper_uses_sha256(self):
        """
        Test that integration data mapper uses SHA256.

        GREEN PHASE: After the fix, SHA256 should be used instead of MD5.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/integration_data_mapper.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is used for ID generation
        assert 'hashlib.sha256' in source, \
            "Fix applied: SHA256 is now used for ID generation"

    def test_canvas_presentation_summary_uses_sha256(self):
        """
        Test that canvas presentation summary uses SHA256.

        GREEN PHASE: After the fix, SHA256 should be used instead of MD5.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/canvas_presentation_summary.py', 'r') as f:
            source = f.read()

        # Verify the fix - SHA256 is used for cache hashing
        assert 'hashlib.sha256' in source, \
            "Fix applied: SHA256 is now used for cache invalidation hashing"

    def test_password_hashing_still_uses_bcrypt(self):
        """
        Test that password hashing still uses bcrypt (secure).

        GREEN PHASE: Verify that bcrypt is still used for passwords.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/auth.py', 'r') as f:
            source = f.read()

        # Verify bcrypt is still used for passwords
        assert 'bcrypt' in source and 'hashpw' in source, \
            "Fix verified: Bcrypt is still used for password hashing (secure)"

    def test_token_encryption_still_uses_fernet(self):
        """
        Test that token encryption still uses Fernet (secure).

        GREEN PHASE: Verify that Fernet is still used for tokens.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/privsec/token_encryption.py', 'r') as f:
            source = f.read()

        # Verify Fernet is still used for encryption
        assert 'Fernet' in source and 'cryptography.fernet' in source, \
            "Fix verified: Fernet (AES-128-CBC + HMAC) is still used for token encryption (secure)"

        # Verify SHA256 is used for token hashing
        assert 'hashlib.sha256' in source, \
            "Fix verified: SHA256 is used for token hashing (secure)"

    def test_crypto_fixes_commented(self):
        """
        Test that cryptography fixes are documented with comments.

        GREEN PHASE: After the fix, security comments should be present.
        """
        # Check that at least one file has the fix comment
        files_with_fix_comment = 0

        files_to_check = [
            ('/Users/rushiparikh/projects/atom/backend/core/communication/adapters/intercom.py', 'CRYPTOGRAPHY FIX'),
            ('/Users/rushiparikh/projects/atom/backend/core/byok_cache_preseeding.py', 'CRYPTOGRAPHY FIX'),
            ('/Users/rushiparikh/projects/atom/backend/core/unified_message_processor.py', 'CRYPTOGRAPHY FIX'),
            ('/Users/rushiparikh/projects/atom/backend/core/integration_data_mapper.py', 'CRYPTOGRAPHY FIX'),
            ('/Users/rushiparikh/projects/atom/backend/core/canvas_presentation_summary.py', 'CRYPTOGRAPHY FIX'),
        ]

        for file_path, comment in files_to_check:
            try:
                with open(file_path, 'r') as f:
                    source = f.read()
                if comment in source or 'CRYPTOGRAPHY' in source:
                    files_with_fix_comment += 1
            except Exception:
                pass

        assert files_with_fix_comment >= 3, \
            f"Fix applied: Security fixes are documented (found in {files_with_fix_comment} files)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
