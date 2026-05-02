"""
Unit Tests for Email Utils

Tests email and data validation utilities:
- validate_email: Email address validation
- validate_email_strict: Strict email validation with error messages
- validate_email_with_plus_addressing: Support for plus addressing
- validate_url: URL validation
- validate_phone: Phone number validation
- validate_uuid: UUID validation
- validate_boolean: Boolean string validation
- parse_boolean: Parse boolean from string
- validate_integer/float: Number validation

Target Coverage: 95%
Target Branch Coverage: 80%+
Pass Rate Target: 100%
"""

import pytest
from core.email_utils import (
    validate_email,
    validate_email_strict,
    validate_email_with_plus_addressing,
    validate_url,
    validate_url_secure,
    validate_phone,
    validate_phone_international,
    validate_uuid,
    validate_boolean,
    parse_boolean,
    validate_integer,
    validate_float
)


# =============================================================================
# Test Class: validate_email
# =============================================================================

class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_email(self):
        """RED: Test valid email address."""
        assert validate_email("user@example.com") is True

    def test_valid_email_with_subdomain(self):
        """RED: Test valid email with subdomain."""
        assert validate_email("user@mail.example.com") is True

    def test_valid_email_with_dots(self):
        """RED: Test valid email with dots in username."""
        assert validate_email("first.last@example.com") is True

    def test_valid_email_with_plus(self):
        """RED: Test valid email with plus addressing."""
        assert validate_email("user+tag@example.com") is True

    def test_valid_email_with_numbers(self):
        """RED: Test valid email with numbers."""
        assert validate_email("user123@example.com") is True

    def test_invalid_email_no_at(self):
        """RED: Test email without @ symbol."""
        assert validate_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """RED: Test email without domain."""
        assert validate_email("user@") is False

    def test_invalid_email_no_user(self):
        """RED: Test email without username."""
        assert validate_email("@example.com") is False

    def test_invalid_email_empty(self):
        """RED: Test empty email."""
        assert validate_email("") is False

    def test_invalid_email_spaces(self):
        """RED: Test email with spaces."""
        assert validate_email("user @example.com") is False


# =============================================================================
# Test Class: validate_email_strict
# =============================================================================

class TestValidateEmailStrict:
    """Tests for validate_email_strict function."""

    def test_valid_email_strict(self):
        """RED: Test strict validation with valid email."""
        valid, error = validate_email_strict("user@example.com")
        assert valid is True
        assert error is None

    def test_invalid_email_strict_no_at(self):
        """RED: Test strict validation catches missing @."""
        valid, error = validate_email_strict("userexample.com")
        assert valid is False
        assert error is not None
        assert "@" in error.lower() or "invalid" in error.lower()

    def test_invalid_email_strict_no_domain(self):
        """RED: Test strict validation catches missing domain."""
        valid, error = validate_email_strict("user@")
        assert valid is False
        assert error is not None

    def test_invalid_email_strict_empty(self):
        """RED: Test strict validation catches empty email."""
        valid, error = validate_email_strict("")
        assert valid is False
        assert error is not None


# =============================================================================
# Test Class: validate_email_with_plus_addressing
# =============================================================================

class TestValidateEmailPlusAddressing:
    """Tests for validate_email_with_plus_addressing function."""

    def test_valid_email_with_plus(self):
        """RED: Test email with plus addressing."""
        assert validate_email_with_plus_addressing("user+tag@example.com") is True

    def test_valid_email_with_multiple_plus(self):
        """RED: Test email with multiple plus signs."""
        assert validate_email_with_plus_addressing("user+tag1+tag2@example.com") is True

    def test_valid_email_without_plus(self):
        """RED: Test regular email still valid."""
        assert validate_email_with_plus_addressing("user@example.com") is True

    def test_valid_email_plus_with_numbers(self):
        """RED: Test plus addressing with numbers."""
        assert validate_email_with_plus_addressing("user+123@example.com") is True


# =============================================================================
# Test Class: validate_url
# =============================================================================

class TestValidateURL:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """RED: Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self):
        """RED: Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_valid_url_with_path(self):
        """RED: Test valid URL with path."""
        assert validate_url("https://example.com/path/to/page") is True

    def test_valid_url_with_query_params(self):
        """RED: Test valid URL with query parameters."""
        assert validate_url("https://example.com?search=test") is True

    def test_valid_url_with_port(self):
        """RED: Test valid URL with port number."""
        assert validate_url("https://example.com:8080") is True

    def test_invalid_url_no_protocol(self):
        """RED: Test URL without protocol."""
        assert validate_url("example.com") is False

    def test_invalid_url_empty(self):
        """RED: Test empty URL."""
        assert validate_url("") is False

    def test_invalid_url_spaces(self):
        """RED: Test URL with spaces."""
        assert validate_url("https://example .com") is False


# =============================================================================
# Test Class: validate_phone
# =============================================================================

class TestValidatePhone:
    """Tests for validate_phone function."""

    def test_valid_phone_us_format(self):
        """RED: Test valid US phone number."""
        assert validate_phone("123-456-7890") is True

    def test_valid_phone_with_parentheses(self):
        """RED: Test phone number with parentheses."""
        assert validate_phone("(123) 456-7890") is True

    def test_valid_phone_plain_digits(self):
        """RED: Test plain 10-digit phone number."""
        assert validate_phone("1234567890") is True

    def test_valid_phone_with_spaces(self):
        """RED: Test phone number with spaces."""
        assert validate_phone("123 456 7890") is True

    def test_invalid_phone_too_short(self):
        """RED: Test phone number with too few digits."""
        assert validate_phone("123456") is False

    def test_invalid_phone_with_letters(self):
        """RED: Test phone number with letters."""
        assert validate_phone("123-456-ABCD") is False

    def test_invalid_phone_empty(self):
        """RED: Test empty phone number."""
        assert validate_phone("") is False


# =============================================================================
# Test Class: validate_uuid
# =============================================================================

class TestValidateUUID:
    """Tests for validate_uuid function."""

    def test_valid_uuid_v4(self):
        """RED: Test valid UUID v4."""
        assert validate_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uuid_uppercase(self):
        """RED: Test valid UUID with uppercase letters."""
        assert validate_uuid("550E8400-E29B-41D4-A716-446655440000") is True

    def test_valid_uuid_mixed_case(self):
        """RED: Test valid UUID with mixed case."""
        assert validate_uuid("550e8400-E29b-41d4-a716-446655440000") is True

    def test_invalid_uuid_no_hyphens(self):
        """RED: Test UUID without hyphens."""
        assert validate_uuid("550e8400e29b41d4a716446655440000") is False

    def test_invalid_uuid_too_short(self):
        """RED: Test UUID that's too short."""
        assert validate_uuid("550e8400") is False

    def test_invalid_uuid_empty(self):
        """RED: Test empty UUID."""
        assert validate_uuid("") is False

    def test_invalid_uuid_with_letters_only(self):
        """RED: Test UUID with only letters."""
        assert validate_uuid("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") is False


# =============================================================================
# Test Class: validate_boolean
# =============================================================================

class TestValidateBoolean:
    """Tests for validate_boolean function."""

    def test_valid_boolean_true(self):
        """RED: Test valid boolean 'true'."""
        assert validate_boolean("true") is True

    def test_valid_boolean_false(self):
        """RED: Test valid boolean 'false'."""
        assert validate_boolean("false") is True

    def test_valid_boolean_yes(self):
        """RED: Test valid boolean 'yes'."""
        assert validate_boolean("yes") is True

    def test_valid_boolean_no(self):
        """RED: Test valid boolean 'no'."""
        assert validate_boolean("no") is True

    def test_valid_boolean_one(self):
        """RED: Test valid boolean '1'."""
        assert validate_boolean("1") is True

    def test_valid_boolean_zero(self):
        """RED: Test valid boolean '0'."""
        assert validate_boolean("0") is True

    def test_invalid_boolean(self):
        """RED: Test invalid boolean value."""
        assert validate_boolean("maybe") is False

    def test_invalid_boolean_empty(self):
        """RED: Test empty boolean string."""
        assert validate_boolean("") is False


# =============================================================================
# Test Class: parse_boolean
# =============================================================================

class TestParseBoolean:
    """Tests for parse_boolean function."""

    def test_parse_true_lower(self):
        """RED: Test parsing 'true'."""
        assert parse_boolean("true") is True

    def test_parse_true_upper(self):
        """RED: Test parsing 'TRUE'."""
        assert parse_boolean("TRUE") is True

    def test_parse_false_lower(self):
        """RED: Test parsing 'false'."""
        assert parse_boolean("false") is False

    def test_parse_yes(self):
        """RED: Test parsing 'yes'."""
        assert parse_boolean("yes") is True

    def test_parse_no(self):
        """RED: Test parsing 'no'."""
        assert parse_boolean("no") is False

    def test_parse_one(self):
        """RED: Test parsing '1'."""
        assert parse_boolean("1") is True

    def test_parse_zero(self):
        """RED: Test parsing '0'."""
        assert parse_boolean("0") is False

    def test_parse_invalid(self):
        """RED: Test parsing invalid value."""
        assert parse_boolean("maybe") is None


# =============================================================================
# Test Class: validate_integer
# =============================================================================

class TestValidateInteger:
    """Tests for validate_integer function."""

    def test_valid_integer(self):
        """RED: Test valid integer."""
        assert validate_integer("123") is True

    def test_valid_negative_integer(self):
        """RED: Test valid negative integer."""
        assert validate_integer("-456") is True

    def test_valid_zero(self):
        """RED: Test zero."""
        assert validate_integer("0") is True

    def test_valid_integer_with_min_max(self):
        """RED: Test integer within range."""
        assert validate_integer("50", min_val=0, max_val=100) is True

    def test_invalid_integer_too_low(self):
        """RED: Test integer below minimum."""
        assert validate_integer("-10", min_val=0) is False

    def test_invalid_integer_too_high(self):
        """RED: Test integer above maximum."""
        assert validate_integer("150", max_val=100) is False

    def test_invalid_integer_with_letters(self):
        """RED: Test integer string with letters."""
        assert validate_integer("12abc") is False

    def test_invalid_integer_empty(self):
        """RED: Test empty integer string."""
        assert validate_integer("") is False


# =============================================================================
# Test Class: validate_float
# =============================================================================

class TestValidateFloat:
    """Tests for validate_float function."""

    def test_valid_float(self):
        """RED: Test valid float."""
        assert validate_float("123.45") is True

    def test_valid_negative_float(self):
        """RED: Test valid negative float."""
        assert validate_float("-456.78") is True

    def test_valid_integer_as_float(self):
        """RED: Test integer value as float."""
        assert validate_float("123") is True

    def test_valid_float_with_min_max(self):
        """RED: Test float within range."""
        assert validate_float("50.5", min_val=0.0, max_val=100.0) is True

    def test_invalid_float_too_low(self):
        """RED: Test float below minimum."""
        assert validate_float("-10.5", min_val=0.0) is False

    def test_invalid_float_too_high(self):
        """RED: Test float above maximum."""
        assert validate_float("150.5", max_val=100.0) is False

    def test_invalid_float_with_letters(self):
        """RED: Test float string with letters."""
        assert validate_float("12.34abc") is False

    def test_invalid_float_empty(self):
        """RED: Test empty float string."""
        assert validate_float("") is False


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
