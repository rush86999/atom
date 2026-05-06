"""
Test suite for core.agent_utils module.

This module tests agent utility functions including:
- React response parsing (Thought, Action, Final Answer extraction)
- Agent ID formatting and parsing
- Maturity level formatting
- Date/time formatters
- Number/currency formatters
- string formatters

All functions in this module are synchronous and use pure functions,
making them ideal for comprehensive unit testing.

Test Strategy:
- Test each function with valid inputs
- Test edge cases (empty strings, None, malformed data)
- Test error handling (ValueError for invalid JSON, etc.)
- Use pytest fixtures for common test data
"""

from datetime import datetime, timedelta, timezone
import pytest
from core.agent_utils import (
    parse_react_response,
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


# ==============================================================================
# React Response Parsing Tests
# ==============================================================================

class TestReactResponseParsing:
    """Test LLM React-style response parsing."""

    def test_parse_react_response_with_thought_and_action(self):
        """Parse response with Thought and Action."""
        llm_output = '''Thought: I need to search for information.
Action: {"tool": "search", "params": {"query": "test"}}'''

        thought, action, final_answer = parse_react_response(llm_output)

        assert thought == "I need to search for information."
        assert action is not None
        assert action["tool"] == "search"
        assert action["params"]["query"] == "test"
        assert final_answer is None

    def test_parse_react_response_with_final_answer(self):
        """Parse response with Final Answer."""
        llm_output = '''Thought: I have found the info.
Final Answer: The answer is 42.'''

        thought, action, final_answer = parse_react_response(llm_output)

        assert thought == "I have found the info."
        assert action is None
        assert final_answer == "The answer is 42."

    def test_parse_react_response_with_json_action(self):
        """Parse response with complex JSON action."""
        llm_output = '''Thought: I need to create a calendar event.
Action: {
    "tool": "calendar_create",
    "params": {
        "title": "Team Meeting",
        "date": "2026-05-10",
        "duration": 60
    }
}'''

        thought, action, final_answer = parse_react_response(llm_output)

        assert action is not None
        assert action["tool"] == "calendar_create"
        assert action["params"]["title"] == "Team Meeting"
        assert action["params"]["duration"] == 60

    def test_parse_react_response_invalid_json_raises_error(self):
        """Invalid JSON in Action raises ValueError."""
        llm_output = '''Action: {invalid json}'''

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_react_response(llm_output)

    def test_parse_react_response_no_thought_defaults_to_text(self):
        """Response without explicit Thought defaults to text before Action."""
        llm_output = '''I need to search.
Action: {"tool": "search"}'''

        thought, action, final_answer = parse_react_response(llm_output)

        assert thought == "I need to search."
        assert action is not None

    def test_parse_react_response_action_without_json_raises_error(self):
        """Action without JSON structure raises ValueError."""
        llm_output = '''Action: just text without json'''

        with pytest.raises(ValueError, match="no JSON structure found"):
            parse_react_response(llm_output)

    def test_parse_react_response_empty_input(self):
        """Empty input returns empty string for thought (default behavior)."""
        thought, action, final_answer = parse_react_response("")

        # Empty string defaults to empty thought, not None
        assert thought == ""
        assert action is None
        assert final_answer is None

    def test_parse_react_response_whitespace_handling(self):
        """Extra whitespace is handled correctly."""
        llm_output = '''
    Thought: I need to search.

    Action: {"tool": "search"}
    '''

        thought, action, final_answer = parse_react_response(llm_output)

        assert thought == "I need to search."
        assert action is not None

    def test_parse_react_response_multiline_thought(self):
        """Thought can span multiple lines."""
        llm_output = '''Thought: I need to search for information.
The user is looking for test data.
Action: {"tool": "search"}'''

        thought, action, final_answer = parse_react_response(llm_output)

        assert "I need to search for information" in thought
        assert "The user is looking for test data" in thought
        assert action is not None


# ==============================================================================
# Agent ID Formatting Tests
# ==============================================================================

class TestAgentIdFormatting:
    """Test agent ID formatting and parsing."""

    def test_format_agent_id_standard_format(self):
        """Format standard agent ID."""
        result = format_agent_id("agent-abc123")
        assert result == "Agent Abc123"

    def test_format_agent_id_with_hyphens(self):
        """Format agent ID with hyphens."""
        result = format_agent_id("workflow-test-workflow")
        assert result == "Workflow Test Workflow"

    def test_format_agent_id_with_underscores(self):
        """Format agent ID with underscores."""
        result = format_agent_id("agent_test_name")
        assert result == "Agent Test Name"

    def test_format_agent_id_empty_string(self):
        """Empty string returns 'Unknown Agent'."""
        result = format_agent_id("")
        assert result == "Unknown Agent"

    def test_format_agent_id_preserves_original(self):
        """Agent ID components are preserved in formatting."""
        result = format_agent_id("special-agent-v2")
        assert "Special" in result
        assert "Agent" in result
        assert "V2" in result


class TestAgentIdParsing:
    """Test agent ID parsing into components."""

    def test_parse_agent_id_standard(self):
        """Parse standard agent ID."""
        result = parse_agent_id("agent-abc123")
        assert result["type"] == "agent"
        assert result["id"] == "abc123"
        assert result["version"] is None

    def test_parse_agent_id_with_version(self):
        """Parse agent ID with version."""
        result = parse_agent_id("workflow-v2-test")
        assert result["type"] == "workflow"
        assert result["id"] == "test"
        assert result["version"] == "v2"

    def test_parse_agent_id_empty_string(self):
        """Empty string returns None for all components."""
        result = parse_agent_id("")
        assert result["type"] is None
        assert result["id"] is None
        assert result["version"] is None

    def test_parse_agent_id_version_only(self):
        """Parse ID with version component."""
        result = parse_agent_id("agent-v1")
        assert result["type"] == "agent"
        assert result["version"] == "v1"


# ==============================================================================
# Maturity Level Formatting Tests
# ==============================================================================

class TestMaturityLevelFormatting:
    """Test maturity level formatting."""

    def test_format_maturity_student(self):
        """Format STUDENT maturity level."""
        result = format_maturity_level("STUDENT")
        assert result == "Student Agent"

    def test_format_maturity_intern(self):
        """Format INTERN maturity level."""
        result = format_maturity_level("INTERN")
        assert result == "Intern Agent"

    def test_format_maturity_supervised(self):
        """Format SUPERVISED maturity level."""
        result = format_maturity_level("SUPERVISED")
        assert result == "Supervised Agent"

    def test_format_maturity_autonomous(self):
        """Format AUTONOMOUS maturity level."""
        result = format_maturity_level("AUTONOMOUS")
        assert result == "Autonomous Agent"

    def test_format_maturity_unknown(self):
        """Unknown maturity level gets capitalized."""
        result = format_maturity_level("custom")
        assert result == "Custom Agent"


# ==============================================================================
# Date/Time Formatter Tests
# ==============================================================================

class TestDateTimeFormatters:
    """Test date and time formatting functions."""

    def test_format_date_iso_valid(self):
        """Format valid ISO date string."""
        result = format_date_iso("2026-03-08")
        assert result == "March 8, 2026"

    def test_format_date_iso_invalid(self):
        """Invalid date string returns original."""
        result = format_date_iso("invalid-date")
        assert result == "invalid-date"

    def test_format_datetime_valid(self):
        """Format valid ISO datetime string."""
        result = format_datetime("2026-03-08T14:30:00")
        assert "March 8, 2026" in result
        assert "2:30 PM" in result

    def test_format_datetime_with_zulu(self):
        """Format datetime with Z timezone."""
        result = format_datetime("2026-03-08T14:30:00Z")
        assert "March 8, 2026" in result

    def test_format_timestamp_valid(self):
        """Format valid Unix timestamp."""
        # March 8, 2026 12:00:00 UTC
        timestamp = 1772974400
        result = format_timestamp(timestamp)
        assert "March 8, 2026" in result

    def test_format_timestamp_invalid(self):
        """Invalid timestamp returns string representation."""
        result = format_timestamp("invalid")
        assert result == "invalid"

    def test_format_relative_time_just_now(self):
        """Format very recent timestamp as 'just now'."""
        now = datetime.now(timezone.utc)
        timestamp = now.timestamp() - 30  # 30 seconds ago
        result = format_relative_time(timestamp)
        assert result == "just now"

    def test_format_relative_time_minutes(self):
        """Format timestamp as minutes ago."""
        now = datetime.now(timezone.utc)
        timestamp = now.timestamp() - 1800  # 30 minutes ago
        result = format_relative_time(timestamp)
        assert result == "30 minutes ago"

    def test_format_relative_time_hours(self):
        """Format timestamp as hours ago."""
        now = datetime.now(timezone.utc)
        timestamp = now.timestamp() - 7200  # 2 hours ago
        result = format_relative_time(timestamp)
        assert result == "2 hours ago"

    def test_format_relative_time_days(self):
        """Format timestamp as days ago."""
        now = datetime.now(timezone.utc)
        timestamp = now.timestamp() - 172800  # 2 days ago
        result = format_relative_time(timestamp)
        assert result == "2 days ago"


# ==============================================================================
# Number/Currency Formatter Tests
# ==============================================================================

class TestCurrencyFormatters:
    """Test currency formatting functions."""

    def test_format_currency_usd_positive(self):
        """Format positive USD amount."""
        result = format_currency_usd(1000)
        assert result == "$1,000.00"

    def test_format_currency_usd_negative(self):
        """Format negative USD amount."""
        result = format_currency_usd(-500)
        assert result == "-$500.00"

    def test_format_currency_usd_zero(self):
        """Format zero USD amount."""
        result = format_currency_usd(0)
        assert result == "$0.00"

    def test_format_currency_eur_positive(self):
        """Format positive EUR amount."""
        result = format_currency_eur(1000)
        assert result == "€1,000.00"

    def test_format_currency_eur_negative(self):
        """Format negative EUR amount (EUR format puts minus after symbol)."""
        result = format_currency_eur(-500)
        # EUR format: €-500.00 (minus after symbol, not before)
        assert result == "€-500.00"

    def test_format_number_large(self):
        """Format large number with separators."""
        result = format_number(1000000)
        assert result == "1,000,000"

    def test_format_percentage_default(self):
        """Format percentage with default decimals."""
        result = format_percentage(0.505)
        assert result == "50.5%"

    def test_format_percentage_custom_decimals(self):
        """Format percentage with custom decimals."""
        result = format_percentage(0.505, 2)
        assert result == "50.50%"

    def test_format_decimal_default(self):
        """Format decimal with default precision."""
        result = format_decimal(3.14159, 2)
        assert result == "3.14"

    def test_format_decimal_high_precision(self):
        """Format decimal with high precision."""
        result = format_decimal(3.14159265, 5)
        assert result == "3.14159"


# ==============================================================================
# String Formatter Tests
# ==============================================================================

class TestStringFormatters:
    """Test string formatting functions."""

    def test_format_phone_10_digits(self):
        """Format 10-digit phone number."""
        result = format_phone("1234567890")
        assert result == "(123) 456-7890"

    def test_format_phone_11_digits_with_country(self):
        """Format 11-digit phone number with country code."""
        result = format_phone("11234567890")
        assert result == "+1 (123) 456-7890"

    def test_format_phone_empty(self):
        """Empty phone number returns empty string."""
        result = format_phone("")
        assert result == ""

    def test_format_name_simple(self):
        """Format simple name."""
        result = format_name("john doe")
        assert result == "John Doe"

    def test_format_name_multiple_words(self):
        """Format name with multiple words."""
        result = format_name("john middle doe")
        assert result == "John Middle Doe"

    def test_truncate_text_short(self):
        """Truncate short text."""
        result = truncate_text("This is a very long text", 10)
        assert result == "This is..."
        assert len(result) == 10

    def test_truncate_text_fits(self):
        """Text that fits is not truncated."""
        result = truncate_text("Short", 20)
        assert result == "Short"

    def test_truncate_text_empty(self):
        """Empty text returns empty string."""
        result = truncate_text("", 10)
        assert result == ""

    def test_sanitize_string_remove_html(self):
        """Sanitize string by removing HTML."""
        result = sanitize_string("<p>Hello</p>", remove_html=True)
        assert result == "Hello"

    def test_sanitize_string_remove_special(self):
        """Sanitize string by removing special characters."""
        result = sanitize_string("Hello@World!", remove_special=True)
        assert result == "HelloWorld"

    def test_sanitize_string_both(self):
        """Sanitize string removing both HTML and special chars."""
        result = sanitize_string("<p>Hello@World!</p>", remove_html=True, remove_special=True)
        assert result == "HelloWorld"

    def test_sanitize_string_keep_html(self):
        """Keep HTML tags when remove_html is False."""
        result = sanitize_string("<p>Hello</p>", remove_html=False)
        assert result == "<p>Hello</p>"
