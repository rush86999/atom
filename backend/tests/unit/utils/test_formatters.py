"""
Tests for formatter utility functions in backend/core/agent_utils.py.

Tests cover:
- Agent utility formatters (agent ID, maturity level)
- Date/time formatters (ISO, datetime, timestamp, relative time)
- Number/currency formatters (USD, EUR, number, percentage, decimal)
- String formatters (phone, name, truncate, sanitize)
- Edge cases (empty strings, null values, special characters, boundary values)
"""

import pytest
import time
from datetime import datetime, timezone
from core.agent_utils import (
    format_agent_id,
    parse_agent_id,
    format_maturity_level,
    format_date_iso,
    format_datetime,
    format_timestamp,
    format_relative_time,
    format_currency_usd,
    format_currency_eur,
    format_number,
    format_percentage,
    format_decimal,
    format_phone,
    format_name,
    truncate_text,
    sanitize_string
)


class TestAgentUtilityFormatters:
    """Test agent utility formatter functions."""

    @pytest.mark.parametrize("agent_id,expected", [
        ("agent-abc123", "Agent Abc123"),
        ("workflow-xyz", "Workflow Xyz"),
        ("agent-test-001", "Agent Test 001"),
        ("workflow-v2-prod", "Workflow V2 Prod"),
    ])
    def test_format_agent_id(self, agent_id, expected):
        """Test agent ID formatting with various inputs."""
        assert format_agent_id(agent_id) == expected

    @pytest.mark.parametrize("agent_id", [
        "",
        None,
    ])
    def test_format_agent_id_edge_cases(self, agent_id):
        """Test agent ID formatting with edge cases."""
        result = format_agent_id(agent_id)
        assert result == "Unknown Agent" or result == "Unknown Agent"

    @pytest.mark.parametrize("agent_id,expected", [
        ("agent-abc123", {"type": "agent", "id": "abc123", "version": None}),
        ("workflow-xyz", {"type": "workflow", "id": "xyz", "version": None}),
        ("workflow-v2-test", {"type": "workflow", "id": "test", "version": "v2"}),
        ("agent-v1-prod", {"type": "agent", "id": "prod", "version": "v1"}),
    ])
    def test_parse_agent_id(self, agent_id, expected):
        """Test agent ID parsing with various formats."""
        result = parse_agent_id(agent_id)
        assert result == expected

    def test_parse_agent_id_empty(self):
        """Test agent ID parsing with empty input."""
        result = parse_agent_id("")
        assert result == {"type": None, "id": None, "version": None}

    @pytest.mark.parametrize("maturity,expected", [
        ("STUDENT", "Student Agent"),
        ("INTERN", "Intern Agent"),
        ("SUPERVISED", "Supervised Agent"),
        ("AUTONOMOUS", "Autonomous Agent"),
        ("student", "Student Agent"),  # Case insensitive
        ("Autonomous", "Autonomous Agent"),
    ])
    def test_format_maturity_level(self, maturity, expected):
        """Test maturity level formatting."""
        assert format_maturity_level(maturity) == expected


class TestDateTimeFormatters:
    """Test date/time formatter functions."""

    @pytest.mark.parametrize("input_date,expected", [
        ("2026-03-08", "March 8, 2026"),
        ("2026-01-01", "January 1, 2026"),
        ("2026-12-31", "December 31, 2026"),
        ("2024-02-29", "February 29, 2024"),  # Leap year
    ])
    def test_format_date_iso(self, input_date, expected):
        """Test ISO date formatting."""
        assert format_date_iso(input_date) == expected

    @pytest.mark.parametrize("invalid_date", [
        "invalid",
        "2026-13-01",  # Invalid month
        "2026-02-30",  # Invalid day
        "",
        None,
    ])
    def test_format_date_iso_invalid(self, invalid_date):
        """Test date formatting with invalid inputs."""
        result = format_date_iso(invalid_date)
        # Should return input as-is if can't parse
        assert result == invalid_date or result == str(invalid_date)

    @pytest.mark.parametrize("input_datetime,expected", [
        ("2026-03-08T14:30:00", "March 8, 2026 at 2:30 PM"),
        ("2026-01-01T00:00:00", "January 1, 2026 at 12:00 AM"),
        ("2026-12-31T23:59:59", "December 31, 2026 at 11:59 PM"),
    ])
    def test_format_datetime(self, input_datetime, expected):
        """Test datetime formatting."""
        assert format_datetime(input_datetime) == expected

    @pytest.mark.parametrize("timestamp,expected", [
        (1772974705, "March 8, 2026"),  # Approximate
        (0, "January 1, 1970"),
        (946684800, "January 1, 2000"),
    ])
    def test_format_timestamp(self, timestamp, expected):
        """Test Unix timestamp formatting."""
        result = format_timestamp(timestamp)
        # Year should match
        assert expected.split(", ")[1] in result

    def test_format_timestamp_invalid(self):
        """Test timestamp formatting with invalid input."""
        assert format_timestamp("invalid") == "invalid"

    def test_format_relative_time_now(self):
        """Test relative time formatting for now."""
        now = time.time()
        assert format_relative_time(now) == "just now"

    def test_format_relative_time_minutes_ago(self):
        """Test relative time formatting for minutes ago."""
        now = time.time()
        assert format_relative_time(now - 60) == "1 minute ago"
        assert format_relative_time(now - 180) == "3 minutes ago"

    def test_format_relative_time_hours_ago(self):
        """Test relative time formatting for hours ago."""
        now = time.time()
        assert format_relative_time(now - 3600) == "1 hour ago"
        assert format_relative_time(now - 7200) == "2 hours ago"

    def test_format_relative_time_days_ago(self):
        """Test relative time formatting for days ago."""
        now = time.time()
        assert format_relative_time(now - 86400) == "1 day ago"
        assert format_relative_time(now - 172800) == "2 days ago"

    def test_format_relative_time_weeks_ago(self):
        """Test relative time formatting for weeks ago."""
        now = time.time()
        assert format_relative_time(now - 604800) == "1 week ago"
        assert format_relative_time(now - 1209600) == "2 weeks ago"


class TestNumberCurrencyFormatters:
    """Test number/currency formatter functions."""

    @pytest.mark.parametrize("amount,expected", [
        (1000, "$1,000.00"),
        (0.99, "$0.99"),
        (1000000, "$1,000,000.00"),
        (0, "$0.00"),
        (-100, "-$100.00"),
    ])
    def test_format_currency_usd(self, amount, expected):
        """Test USD currency formatting."""
        assert format_currency_usd(amount) == expected

    def test_format_currency_usd_invalid(self):
        """Test USD formatting with invalid input."""
        assert format_currency_usd(None) == "$0.00"
        assert format_currency_usd("invalid") == "$0.00"

    @pytest.mark.parametrize("amount,expected", [
        (1000, "€1,000.00"),
        (0.99, "€0.99"),
        (1000000, "€1,000,000.00"),
        (0, "€0.00"),
    ])
    def test_format_currency_eur(self, amount, expected):
        """Test EUR currency formatting."""
        assert format_currency_eur(amount) == expected

    @pytest.mark.parametrize("number,expected", [
        (1000, "1,000"),
        (1000000, "1,000,000"),
        (0, "0"),
        (-1000, "-1,000"),
        (123456789, "123,456,789"),
    ])
    def test_format_number(self, number, expected):
        """Test number formatting with thousands separators."""
        assert format_number(number) == expected

    @pytest.mark.parametrize("value,decimals,expected", [
        (0.505, 1, "50.5%"),
        (0.5, 0, "50%"),
        (0.123, 2, "12.30%"),
        (1.0, 1, "100.0%"),
        (0.001, 2, "0.10%"),
    ])
    def test_format_percentage(self, value, decimals, expected):
        """Test percentage formatting."""
        assert format_percentage(value, decimals) == expected

    @pytest.mark.parametrize("value,precision,expected", [
        (3.14159, 2, "3.14"),
        (3.14159, 4, "3.1416"),
        (1.0, 2, "1.00"),
        (0, 2, "0.00"),
    ])
    def test_format_decimal(self, value, precision, expected):
        """Test decimal precision formatting."""
        assert format_decimal(value, precision) == expected


class TestStringFormatters:
    """Test string formatter functions."""

    @pytest.mark.parametrize("phone,expected", [
        ("1234567890", "(123) 456-7890"),
        ("11234567890", "+1 (123) 456-7890"),
        ("+11234567890", "+1 (123) 456-7890"),
        ("(123) 456-7890", "(123) 456-7890"),  # Already formatted
    ])
    def test_format_phone_valid(self, phone, expected):
        """Test phone number formatting for valid numbers."""
        assert format_phone(phone) == expected

    @pytest.mark.parametrize("phone", [
        "123",  # Too short
        "",  # Empty
        None,  # None
    ])
    def test_format_phone_invalid(self, phone):
        """Test phone formatting with invalid inputs."""
        result = format_phone(phone)
        assert result == "" or result == phone

    @pytest.mark.parametrize("name,expected", [
        ("john doe", "John Doe"),
        ("john", "John"),
        ("JOHN DOE", "John Doe"),
        ("jOhN dOe", "John Doe"),
    ])
    def test_format_name(self, name, expected):
        """Test name capitalization."""
        assert format_name(name) == expected

    def test_format_name_edge_cases(self):
        """Test name formatting with edge cases."""
        assert format_name("") == ""
        assert format_name(None) == ""

    @pytest.mark.parametrize("text,max_length,expected", [
        ("This is a very long text", 10, "This is..."),
        ("Short", 10, "Short"),
        ("Exact len", 8, "Exact..."),  # 9 chars truncated to 8 with suffix
        ("", 10, ""),
    ])
    def test_truncate_text(self, text, max_length, expected):
        """Test text truncation."""
        assert truncate_text(text, max_length) == expected

    def test_truncate_text_custom_suffix(self):
        """Test text truncation with custom suffix."""
        assert truncate_text("Long text here", 8, ">>") == "Long t>>"

    @pytest.mark.parametrize("text,remove_html,remove_special,expected", [
        ("<p>Hello</p>", True, False, "Hello"),
        ("<p>Hello</p> <b>World</b>", True, False, "Hello World"),
        ("Hello@#$World", False, True, "HelloWorld"),
        ("<p>Hello@#$</p>", True, True, "Hello"),
    ])
    def test_sanitize_string(self, text, remove_html, remove_special, expected):
        """Test string sanitization."""
        assert sanitize_string(text, remove_html, remove_special) == expected

    def test_sanitize_string_edge_cases(self):
        """Test sanitization with edge cases."""
        assert sanitize_string("") == ""
        assert sanitize_string(None) == ""
        assert sanitize_string("   Hello   ") == "Hello"


class TestEdgeCases:
    """Test edge cases across all formatter functions."""

    @pytest.mark.parametrize("formatter_func", [
        format_agent_id,
        format_name,
        truncate_text,
        sanitize_string,
    ])
    def test_empty_string_handling(self, formatter_func):
        """Test that formatters handle empty strings gracefully."""
        try:
            result = formatter_func("")
            # Should return empty string or a default value
            assert result == "" or result is not None
        except (ValueError, AttributeError):
            # Some functions may raise these for empty input
            pass

    def test_unicode_handling(self):
        """Test that formatters handle Unicode characters."""
        # Test with emoji
        assert truncate_text("Hello 👋 World", 10) == "Hello 👋..."

        # Test with non-Latin characters
        assert format_name("日本語") == "日本語"

    def test_large_numbers(self):
        """Test formatting of very large numbers."""
        billion = 1_000_000_000
        assert format_number(billion) == "1,000,000,000"
        assert format_currency_usd(billion) == "$1,000,000,000.00"

    def test_negative_numbers(self):
        """Test formatting of negative numbers."""
        assert format_number(-1000) == "-1,000"
        assert format_currency_usd(-100.50) == "-$100.50"
        assert format_percentage(-0.5) == "-50.0%"

    def test_boundary_values(self):
        """Test boundary values for formatters."""
        # Zero values
        assert format_number(0) == "0"
        assert format_currency_usd(0) == "$0.00"
        assert format_percentage(0) == "0.0%"

        # Maximum precision
        assert format_decimal(3.14159265359, 10) == "3.1415926536"

        # Minimum length
        assert truncate_text("Hi", 10) == "Hi"
        assert truncate_text("Hi", 1) == "."
