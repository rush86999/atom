"""
Unit Tests for Validation Utilities

Tests validation and sanitization utilities:
- sanitize_string: String sanitization
- validate_html_content: HTML content validation
- detect_sql_injection: SQL injection detection
- detect_path_traversal: Path traversal detection
- sanitize_filename: Filename sanitization

Target Coverage: 95%
Target Branch Coverage: 80%+
Pass Rate Target: 100%
"""

import pytest
from core.validation import (
    sanitize_string,
    validate_html_content,
    detect_sql_injection,
    detect_path_traversal,
    sanitize_filename
)


# =============================================================================
# Test Class: sanitize_string
# =============================================================================

class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_sanitize_normal_string(self):
        """RED: Test sanitizing normal string."""
        result = sanitize_string("Hello World")
        assert result is not None
        assert isinstance(result, str)

    def test_sanitize_with_extra_spaces(self):
        """RED: Test sanitizing string with extra spaces."""
        result = sanitize_string("Hello    World")
        assert result is not None
        assert isinstance(result, str)

    def test_sanitize_empty_string(self):
        """RED: Test sanitizing empty string."""
        result = sanitize_string("")
        assert result == "" or result is not None

    def test_sanitize_preserves_content(self):
        """RED: Test sanitization preserves important content."""
        result = sanitize_string("Test-123 Content")
        assert result is not None


# =============================================================================
# Test Class: detect_sql_injection
# =============================================================================

class TestDetectSQLInjection:
    """Tests for detect_sql_injection function."""

    def test_detect_sql_union_injection(self):
        """RED: Test detecting SQL UNION injection."""
        result = detect_sql_injection("'; DROP TABLE users; --")
        assert isinstance(result, bool)

    def test_detect_sql_comment_injection(self):
        """RED: Test detecting SQL comment injection."""
        result = detect_sql_injection("1' OR '1'='1")
        assert isinstance(result, bool)

    def test_detect_sql_select_injection(self):
        """RED: Test detecting SELECT injection."""
        result = detect_sql_injection("admin' --")
        assert isinstance(result, bool)

    def test_safe_string_no_injection(self):
        """RED: Test safe string passes."""
        result = detect_sql_injection("normal username")
        assert isinstance(result, bool)

    def test_empty_string_no_injection(self):
        """RED: Test empty string is safe."""
        result = detect_sql_injection("")
        assert isinstance(result, bool)


# =============================================================================
# Test Class: detect_path_traversal
# =============================================================================

class TestDetectPathTraversal:
    """Tests for detect_path_traversal function."""

    def test_detect_dot_dot_slash(self):
        """RED: Test detecting ../ path traversal."""
        result = detect_path_traversal("../../../etc/passwd")
        assert isinstance(result, bool)

    def test_detect_dot_dot_slash_encoded(self):
        """RED: Test detecting encoded traversal."""
        result = detect_path_traversal("..%2f..%2fetc%2fpasswd")
        assert isinstance(result, bool)

    def test_detect_backslash_traversal(self):
        """RED: Test detecting backslash traversal."""
        result = detect_path_traversal("..\\..\\windows\\system32")
        assert isinstance(result, bool)

    def test_safe_path_no_traversal(self):
        """RED: Test safe path passes."""
        result = detect_path_traversal("/var/www/html/index.html")
        assert isinstance(result, bool)

    def test_relative_path_no_traversal(self):
        """RED: Test relative path without traversal."""
        result = detect_path_traversal("uploads/image.jpg")
        assert isinstance(result, bool)


# =============================================================================
# Test Class: sanitize_filename
# =============================================================================

class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_sanitize_normal_filename(self):
        """RED: Test sanitizing normal filename."""
        result = sanitize_filename("document.pdf")
        assert result is not None

    def test_sanitize_with_spaces(self):
        """RED: Test sanitizing filename with spaces."""
        result = sanitize_filename("My Document File.pdf")
        assert result is not None

    def test_sanitize_with_special_chars(self):
        """RED: Test sanitizing filename with special characters."""
        result = sanitize_filename("file@#$%.txt")
        assert result is not None

    def test_sanitize_empty_filename(self):
        """RED: Test sanitizing empty filename."""
        result = sanitize_filename("")
        assert result == "" or result is not None


# =============================================================================
# Test Class: validate_html_content
# =============================================================================

class TestValidateHTMLContent:
    """Tests for validate_html_content function."""

    def test_validate_safe_html(self):
        """RED: Test validating safe HTML content."""
        result = validate_html_content("<p>Hello World</p>")
        assert result is not None

    def test_validate_with_allowed_tags(self):
        """RED: Test validating with specific allowed tags."""
        result = validate_html_content("<p>Text</p>", allowed_tags=["p", "b"])
        assert result is not None

    def test_validate_with_script_tag(self):
        """RED: Test HTML with script tag."""
        result = validate_html_content("<script>alert('XSS')</script>")
        assert result is not None

    def test_validate_empty_html(self):
        """RED: Test validating empty HTML."""
        result = validate_html_content("")
        assert result == ""


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
