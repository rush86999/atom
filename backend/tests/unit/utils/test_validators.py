"""
Tests for validator utility functions in backend/core/email_utils.py.

Tests cover:
- Email validators (basic, strict, + addressing)
- URL validators (basic, with params, secure HTTPS)
- Phone validators (US format, international)
- UUID validators (v4, any version)
- General validators (boolean, integer, float, JSON)
- Edge cases (empty strings, null values, malformed inputs)
"""

import pytest
from core.email_utils import (
    validate_email,
    validate_email_strict,
    validate_email_with_plus_addressing,
    validate_url,
    validate_url_with_params,
    validate_url_secure,
    validate_phone,
    validate_phone_international,
    validate_uuid,
    validate_uuid_any_version,
    validate_boolean,
    parse_boolean,
    validate_integer,
    validate_float,
    validate_json
)


class TestEmailValidators:
    """Test email validation functions."""

    @pytest.mark.parametrize("valid_email", [
        "user@example.com",
        "test.user@example.com",
        "user+tag@example.com",
        "user123@example.org",
        "first.last@subdomain.example.com",
        "user@example.co.uk",
    ])
    def test_validate_email_valid(self, valid_email):
        """Test email validation with valid emails."""
        assert validate_email(valid_email) is True

    @pytest.mark.parametrize("invalid_email", [
        "plainaddress",
        "@missingusername.com",
        "username@.com",
        "username@com",
        "",
        None,
        "username@.com.",
        "username@",
        "@example.com",
        "double@@example.com",
    ])
    def test_validate_email_invalid(self, invalid_email):
        """Test email validation with invalid emails."""
        assert validate_email(invalid_email) is False

    def test_validate_email_strict_valid(self):
        """Test strict email validation with valid email."""
        is_valid, error = validate_email_strict("user@example.com")
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("invalid_email,expected_error", [
        ("", "Email is required"),
        (None, "Email must be a string"),
        ("invalid", "Email must contain @ symbol"),
        ("@example.com", "Email must have username before @"),
        ("user@", "Email must have domain after @"),
        ("user@domain", "Email domain must contain extension"),
    ])
    def test_validate_email_strict_invalid(self, invalid_email, expected_error):
        """Test strict email validation with detailed errors."""
        is_valid, error = validate_email_strict(invalid_email)
        assert is_valid is False
        assert error == expected_error

    @pytest.mark.parametrize("email", [
        "user+tag@example.com",
        "user+test+tag@example.com",
        "user@example.com",
    ])
    def test_validate_email_with_plus_addressing(self, email):
        """Test email validation with + addressing support."""
        assert validate_email_with_plus_addressing(email) is True


class TestURLValidators:
    """Test URL validation functions."""

    @pytest.mark.parametrize("valid_url", [
        "https://example.com",
        "http://example.com",
        "https://www.example.com",
        "https://example.com/path",
        "https://example.com?query=value",
        "https://example.com#section",
        "ftp://example.com",
        "https://subdomain.example.com",
        "https://example.co.uk",
    ])
    def test_validate_url_valid(self, valid_url):
        """Test URL validation with valid URLs."""
        assert validate_url(valid_url) is True

    @pytest.mark.parametrize("invalid_url", [
        "example.com",
        "",
        None,
        "https://",
        "http://",
        "//example.com",
        "not a url",
    ])
    def test_validate_url_invalid(self, invalid_url):
        """Test URL validation with invalid URLs."""
        assert validate_url(invalid_url) is False

    def test_validate_url_with_params_valid(self):
        """Test URL validation with params for valid URL."""
        is_valid, error = validate_url_with_params("https://example.com?foo=bar")
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("invalid_url,expected_error", [
        ("", "URL is required"),
        (None, "URL must be a string"),
        ("example.com", "URL must start with http://, https://, or ftp://"),
    ])
    def test_validate_url_with_params_invalid(self, invalid_url, expected_error):
        """Test URL validation with params for invalid URLs."""
        is_valid, error = validate_url_with_params(invalid_url)
        assert is_valid is False
        assert error == expected_error

    @pytest.mark.parametrize("secure_url", [
        "https://example.com",
        "https://example.com/path",
    ])
    def test_validate_url_secure_valid(self, secure_url):
        """Test HTTPS URL validation."""
        assert validate_url_secure(secure_url) is True

    @pytest.mark.parametrize("insecure_url", [
        "http://example.com",
        "ftp://example.com",
        "",
        None,
    ])
    def test_validate_url_secure_invalid(self, insecure_url):
        """Test HTTPS URL validation rejects insecure URLs."""
        assert validate_url_secure(insecure_url) is False


class TestPhoneValidators:
    """Test phone validation functions."""

    @pytest.mark.parametrize("valid_phone", [
        "1234567890",
        "(123) 456-7890",
        "123-456-7890",
        "123.456.7890",
        "123 456 7890",
        "(123)456-7890",
    ])
    def test_validate_phone_valid(self, valid_phone):
        """Test phone validation with valid US numbers."""
        assert validate_phone(valid_phone) is True

    @pytest.mark.parametrize("invalid_phone", [
        "123",
        "123456789012345",
        "",
        None,
        "abcdefghij",
        "123-456-789",  # Too short
    ])
    def test_validate_phone_invalid(self, invalid_phone):
        """Test phone validation with invalid numbers."""
        assert validate_phone(invalid_phone) is False

    @pytest.mark.parametrize("valid_international_phone", [
        "+11234567890",
        "+44 20 7123 4567",
        "+91 98765 43210",
        "+1-123-456-7890",
    ])
    def test_validate_phone_international_valid(self, valid_international_phone):
        """Test international phone validation."""
        assert validate_phone_international(valid_international_phone) is True

    @pytest.mark.parametrize("invalid_phone", [
        "123",
        "12345678901234567890",
        "",
        None,
        "not a phone",
    ])
    def test_validate_phone_international_invalid(self, invalid_phone):
        """Test international phone validation with invalid numbers."""
        assert validate_phone_international(invalid_phone) is False


class TestUUIDValidators:
    """Test UUID validation functions."""

    @pytest.mark.parametrize("valid_uuid", [
        "123e4567-e89b-42d3-a456-426614174000",
        "00000000-0000-4000-8000-000000000000",
        "ffffffff-ffff-4fff-bfff-ffffffffffff",
    ])
    def test_validate_uuid_v4_valid(self, valid_uuid):
        """Test UUID v4 validation with valid UUIDs."""
        assert validate_uuid(valid_uuid) is True

    @pytest.mark.parametrize("invalid_uuid", [
        "123e4567-e89b-42d3-a456-42661417400",  # Too short
        "123e4567-e89b-42d3-a456-4266141740000",  # Too long
        "123e4567-e89b-22d3-a456-426614174000",  # Invalid version (2)
        "123e4567-e89b-42d3-a456-42661417400g",  # Invalid character
        "",
        None,
        "not-a-uuid",
    ])
    def test_validate_uuid_v4_invalid(self, invalid_uuid):
        """Test UUID v4 validation with invalid UUIDs."""
        assert validate_uuid(invalid_uuid) is False

    @pytest.mark.parametrize("valid_uuid", [
        "123e4567-e89b-42d3-a456-426614174000",  # v4
        "123e4567-e89b-22d3-a456-426614174000",  # v2
        "123e4567-e89b-32d3-a456-426614174000",  # v3
        "123e4567-e89b-52d3-a456-426614174000",  # v5
    ])
    def test_validate_uuid_any_version(self, valid_uuid):
        """Test UUID validation (any version)."""
        assert validate_uuid_any_version(valid_uuid) is True


class TestGeneralValidators:
    """Test general validation functions."""

    @pytest.mark.parametrize("valid_bool", [
        "true",
        "false",
        "TRUE",
        "FALSE",
        "1",
        "0",
        "yes",
        "no",
        "YES",
        "NO",
    ])
    def test_validate_boolean_valid(self, valid_bool):
        """Test boolean string validation."""
        assert validate_boolean(valid_bool) is True

    @pytest.mark.parametrize("invalid_bool", [
        "invalid",
        "",
        None,
        "2",
        "maybe",
    ])
    def test_validate_boolean_invalid(self, invalid_bool):
        """Test boolean string validation with invalid inputs."""
        assert validate_boolean(invalid_bool) is False

    @pytest.mark.parametrize("value,expected", [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("invalid", None),
        ("", None),
    ])
    def test_parse_boolean(self, value, expected):
        """Test boolean string parsing."""
        assert parse_boolean(value) == expected

    @pytest.mark.parametrize("valid_int", [
        "123",
        "-123",
        "0",
        "999999",
    ])
    def test_validate_integer_valid(self, valid_int):
        """Test integer string validation."""
        assert validate_integer(valid_int) is True

    @pytest.mark.parametrize("invalid_int", [
        "abc",
        "12.34",
        "",
        None,
    ])
    def test_validate_integer_invalid(self, invalid_int):
        """Test integer validation with invalid inputs."""
        assert validate_integer(invalid_int) is False

    @pytest.mark.parametrize("value,min_val,max_val,expected", [
        ("123", 0, 200, True),
        ("123", 100, 200, True),
        ("99", 0, 200, True),
        ("50", 0, 100, True),
        ("-50", -100, 100, True),
        ("250", 0, 200, False),  # Above max
        ("-50", 0, 200, False),  # Below min
    ])
    def test_validate_integer_with_range(self, value, min_val, max_val, expected):
        """Test integer validation with range checking."""
        assert validate_integer(value, min_val, max_val) == expected

    @pytest.mark.parametrize("valid_float", [
        "123.45",
        "-123.45",
        "0.0",
        "999.999",
        "123",  # Integer is valid float
    ])
    def test_validate_float_valid(self, valid_float):
        """Test float string validation."""
        assert validate_float(valid_float) is True

    @pytest.mark.parametrize("invalid_float", [
        "abc",
        "",
        None,
    ])
    def test_validate_float_invalid(self, invalid_float):
        """Test float validation with invalid inputs."""
        assert validate_float(invalid_float) is False

    @pytest.mark.parametrize("value,min_val,max_val,expected", [
        ("123.45", 0.0, 200.0, True),
        ("99.99", 0.0, 100.0, True),
        ("250.0", 0.0, 200.0, False),  # Above max
        ("-50.0", 0.0, 200.0, False),  # Below min
    ])
    def test_validate_float_with_range(self, value, min_val, max_val, expected):
        """Test float validation with range checking."""
        assert validate_float(value, min_val, max_val) == expected

    @pytest.mark.parametrize("valid_json", [
        '{"key": "value"}',
        '{"number": 123}',
        '{"nested": {"key": "value"}}',
        '[]',
        '{}',
        'null',
        'true',
        'false',
        '123',
        '"string"',
    ])
    def test_validate_json_valid(self, valid_json):
        """Test JSON string validation."""
        assert validate_json(valid_json) is True

    @pytest.mark.parametrize("invalid_json", [
        '{key: value}',  # Missing quotes
        "{'key': 'value'}",  # Single quotes
        '{"key": value}',  # Unquoted value
        '',
        None,
        "not json",
        '{"key": "value"',  # Missing closing brace
    ])
    def test_validate_json_invalid(self, invalid_json):
        """Test JSON validation with invalid inputs."""
        assert validate_json(invalid_json) is False


class TestEdgeCases:
    """Test edge cases across all validator functions."""

    def test_empty_string_handling(self):
        """Test that validators handle empty strings gracefully."""
        assert validate_email("") is False
        assert validate_url("") is False
        assert validate_phone("") is False
        assert validate_uuid("") is False
        assert validate_boolean("") is False
        assert validate_integer("") is False
        assert validate_float("") is False
        assert validate_json("") is False

    def test_none_handling(self):
        """Test that validators handle None gracefully."""
        assert validate_email(None) is False
        assert validate_url(None) is False
        assert validate_phone(None) is False
        assert validate_uuid(None) is False
        assert validate_boolean(None) is False
        assert validate_integer(None) is False
        assert validate_float(None) is False
        assert validate_json(None) is False

    def test_non_string_handling(self):
        """Test that validators handle non-string inputs gracefully."""
        assert validate_email(123) is False
        assert validate_url(123) is False
        assert validate_phone(123) is False
        assert validate_uuid(123) is False
        assert validate_boolean(123) is False
        assert validate_integer(123) is False
        assert validate_float(123) is False
        assert validate_json(123) is False

    def test_unicode_handling(self):
        """Test that validators handle Unicode characters."""
        # Email with Unicode (should fail basic validation)
        assert validate_email("用户@example.com") is False

        # URL with Unicode (should fail basic validation)
        assert validate_url("https://例子.com") is False

    def test_boundary_values(self):
        """Test boundary values for numeric validators."""
        # Integer boundaries
        assert validate_integer("0") is True
        assert validate_integer("-999999999") is True
        assert validate_integer("999999999") is True

        # Float boundaries
        assert validate_float("0.0") is True
        assert validate_float("-999999.999") is True
        assert validate_float("999999.999") is True

    def test_malformed_inputs(self):
        """Test validators with malformed inputs."""
        # Email with multiple @
        assert validate_email("user@@@example.com") is False

        # URL with spaces
        assert validate_url("https://example .com") is False

        # Phone with letters
        assert validate_phone("123-456-789a") is False

        # UUID with wrong separators
        assert validate_uuid("123e4567_e89b_12d3_a456_426614174000") is False
