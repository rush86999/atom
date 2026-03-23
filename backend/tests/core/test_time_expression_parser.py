"""
Tests for Time Expression Parser

Tests for natural language time expression parsing including:
- Pattern-based parsing (daily, hourly, weekly, monthly)
- Time normalization (12h to 24h)
- Error handling
"""

import pytest
from core.time_expression_parser import parse_with_patterns, normalize_time_12h_to_24h, TIME_PATTERNS


class TestParseWithPatterns:
    """Tests for parse_with_patterns function."""

    def test_parse_every_day(self):
        """Test parsing daily expressions."""
        result = parse_with_patterns("every day")
        assert result is not None
        assert result["schedule_type"] == "cron"
        assert "cron_expression" in result

    def test_parse_every_day_at_time(self):
        """Test parsing daily expressions with specific time."""
        result = parse_with_patterns("every day at 9am")
        assert result is not None
        assert result["schedule_type"] == "cron"
        assert "cron_expression" in result

    def test_parse_every_minutes(self):
        """Test parsing minute interval expressions."""
        result = parse_with_patterns("every 5 minutes")
        assert result is not None
        assert result["schedule_type"] == "interval"
        assert result["interval_minutes"] == 5

    def test_parse_every_hours(self):
        """Test parsing hour interval expressions."""
        result = parse_with_patterns("every 2 hours")
        assert result is not None
        assert result["schedule_type"] == "interval"
        assert result["interval_minutes"] == 120  # 2 hours = 120 minutes

    def test_parse_weekdays(self):
        """Test parsing weekday expressions."""
        result = parse_with_patterns("weekdays")
        assert result is not None
        assert result["schedule_type"] == "cron"

    def test_parse_weekends(self):
        """Test parsing weekend expressions."""
        result = parse_with_patterns("weekends")
        assert result is not None
        assert result["schedule_type"] == "cron"

    def test_parse_specific_day(self):
        """Test parsing specific day expressions."""
        result = parse_with_patterns("every monday")
        assert result is not None
        assert result["schedule_type"] == "cron"

    def test_parse_first_day_of_month(self):
        """Test parsing first day of month expressions."""
        result = parse_with_patterns("first day of every month")
        assert result is not None
        assert result["schedule_type"] == "cron"

    def test_parse_no_match(self):
        """Test expression that doesn't match any pattern."""
        result = parse_with_patterns("invalid expression")
        assert result is None

    def test_parse_empty_string(self):
        """Test empty string handling."""
        result = parse_with_patterns("")
        assert result is None


class TestNormalizeTime12hTo24h:
    """Tests for normalize_time_12h_to_24h function."""

    def test_normalize_am_times(self):
        """Test normalizing AM times."""
        assert normalize_time_12h_to_24h(9, 0, "am") == (9, 0)
        assert normalize_time_12h_to_24h(12, 0, "am") == (0, 0)  # Midnight
        assert normalize_time_12h_to_24h(11, 30, "am") == (11, 30)

    def test_normalize_pm_times(self):
        """Test normalizing PM times."""
        assert normalize_time_12h_to_24h(1, 0, "pm") == (13, 0)
        assert normalize_time_12h_to_24h(12, 0, "pm") == (12, 0)  # Noon
        assert normalize_time_12h_to_24h(11, 30, "pm") == (23, 30)

    def test_normalize_no_period(self):
        """Test normalization when no period is provided."""
        assert normalize_time_12h_to_24h(9, 0, None) == (9, 0)
        assert normalize_time_12h_to_24h(14, 30, None) == (14, 30)

    def test_normalize_edge_cases(self):
        """Test edge cases for time normalization."""
        # 11:59 PM should be 23:59
        assert normalize_time_12h_to_24h(11, 59, "pm") == (23, 59)
        # 12:59 AM should be 0:59
        assert normalize_time_12h_to_24h(12, 59, "am") == (0, 59)


class TestTimePatterns:
    """Tests for TIME_PATTERNS constant."""

    def test_time_patterns_is_dict(self):
        """Test that TIME_PATTERNS is a dictionary."""
        assert isinstance(TIME_PATTERNS, dict)

    def test_time_patterns_has_entries(self):
        """Test that TIME_PATTERNS has pattern entries."""
        assert len(TIME_PATTERNS) > 0

    def test_time_patterns_structure(self):
        """Test that TIME_PATTERNS entries have required keys."""
        for pattern, config in TIME_PATTERNS.items():
            assert "type" in config
            assert config["type"] in ["cron", "interval"]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_whitespace_variations(self):
        """Test expressions with different whitespace."""
        result1 = parse_with_patterns("every 5 minutes")
        result2 = parse_with_patterns("every  5  minutes")
        # Both should parse successfully
        assert result1 is not None
        assert result2 is not None

    def test_case_insensitive(self):
        """Test that parsing is case insensitive."""
        result1 = parse_with_patterns("EVERY DAY")
        result2 = parse_with_patterns("every day")
        result3 = parse_with_patterns("Every Day")
        # All should parse successfully
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None

    def test_zero_interval(self):
        """Test zero value in interval expressions."""
        # This may or may not match depending on pattern regex
        result = parse_with_patterns("every 0 minutes")
        # Just verify it doesn't crash
        assert result is None or isinstance(result, dict)


class TestIntegration:
    """Integration tests for time expression parsing."""

    def test_multiple_time_expressions(self):
        """Test parsing multiple different expressions."""
        expressions = [
            "every day",
            "every 5 minutes",
            "every 2 hours",
            "weekdays",
            "every monday",
            "first day of every month"
        ]

        results = [parse_with_patterns(expr) for expr in expressions]

        # All should parse successfully
        assert all(r is not None for r in results)
        assert all("schedule_type" in r for r in results)

    def test_cron_expressions_generated(self):
        """Test that cron expressions are generated for cron-type schedules."""
        result = parse_with_patterns("every day at 9am")
        assert result["schedule_type"] == "cron"
        assert "cron_expression" in result
        assert isinstance(result["cron_expression"], str)

    def test_intervals_generated(self):
        """Test that intervals are generated for interval-type schedules."""
        result = parse_with_patterns("every 15 minutes")
        assert result["schedule_type"] == "interval"
        assert "interval_minutes" in result
        assert isinstance(result["interval_minutes"], int)
