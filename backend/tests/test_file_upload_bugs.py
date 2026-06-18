"""
Test suite for File Upload vulnerabilities.

RED PHASE: These tests expose file upload bugs.

The bugs:
1. accounting/routes.py:156-199 - No file type validation, content scanning, size limits
2. accounting/routes.py:171 - Filename not sanitized (path traversal risk)
3. accounting/routes.py:167-175 - Hardcoded upload path, no size validation
"""

import pytest


class TestFileUploadVulnerabilities:
    """
    Test suite revealing file upload vulnerabilities.

    The bug: File upload endpoint doesn't properly validate files,
    allowing malware upload, path traversal, and resource exhaustion.
    """

    def test_file_upload_missing_type_validation(self):
        """
        Test that file upload doesn't validate file types.

        BUG: Lines 156-183 - No validation of actual file type, only extension.
        An attacker can upload executable files disguised with safe extensions.
        """
        # Read source directly to avoid import errors
        with open('/Users/rushiparikh/projects/atom/backend/accounting/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - file type is inferred from extension only
        assert 'file_ext' in source, \
            "Bug confirmed: File type inferred from extension only"

        # Verify no magic byte validation
        assert 'magic' not in source.lower() and 'mime' not in source.lower(), \
            "Bug confirmed: No magic byte or MIME type validation"

        # Verify no content scanning
        assert 'scan' not in source.lower() and 'virus' not in source.lower(), \
            "Bug confirmed: No malware scanning"

    def test_file_upload_missing_size_limit(self):
        """
        Test that file upload doesn't enforce size limits.

        BUG: Lines 167-175 - No file size validation before saving.
        Allows DoS via large file uploads.
        """
        with open('/Users/rushiparikh/projects/atom/backend/accounting/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - no file size check
        assert 'file.size' not in source and 'content_length' not in source and 'MAX_FILE_SIZE' not in source, \
            "Bug confirmed: No file size validation before saving"

        # Verify no max file size constant
        assert 'MAX_FILE_SIZE' not in source and 'MAX_UPLOAD' not in source, \
            "Bug confirmed: No maximum file size limit defined"

    def test_file_upload_filename_not_sanitized(self):
        """
        Test that filename is not sanitized before use.

        BUG: Line 171 - Uses file.filename directly in file path.
        Could allow path traversal via malicious filenames.
        """
        with open('/Users/rushiparikh/projects/atom/backend/accounting/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - filename used directly
        assert 'file.filename' in source, \
            "Bug confirmed: User-provided filename used directly"

        # Verify no sanitization of filename
        assert 'sanitize' not in source.lower() and 'secure_filename' not in source.lower(), \
            "Bug confirmed: No filename sanitization"

        # Verify path is constructed with user input
        assert 'os.path.join(upload_dir, f"{file_id}{file_ext}")' in source, \
            "Bug confirmed: File path constructed with unsanitized extension"

    def test_file_upload_allows_any_extension(self):
        """
        Test that file upload accepts any file extension.

        BUG: Line 182 - Only checks extension for PDF/image classification.
        Allows .exe, .bat, .sh files which could be malicious.
        """
        with open('/Users/rushiparikh/projects/atom/backend/accounting/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - only checks for pdf/images
        assert 'file_ext.lower() == ".pdf"' in source or \
               'file_type="pdf" if file_ext.lower() == ".pdf"' in source or \
               'file_type="image"' in source, \
            "Bug confirmed: Limited file type check, other extensions allowed"

        # Verify no whitelist of allowed extensions
        assert 'ALLOWED_EXTENSIONS' not in source and 'ALLOWED_EXT' not in source, \
            "Bug confirmed: No whitelist of allowed extensions"

    def test_file_upload_no_content_validation(self):
        """
        Test that uploaded files are not scanned for malware.

        BUG: Lines 174-183 - Files saved directly without content scanning.
        """
        with open('/Users/rushiparikh/projects/atom/backend/accounting/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - file saved directly without scanning
        assert 'shutil.copyfileobj' in source, \
            "Bug confirmed: File saved without content validation"

        # Verify no integration with security scanner
        assert 'security_scanner' not in source.lower() and 'scan' not in source.lower(), \
            "Bug confirmed: No integration with security scanner"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
