"""
Tests for TimeExpressionParser

Tests for time expression parsing including:
- Time unit parsing (minutes, hours, days, weeks)
- Expression validation
- Duration calculation
- Error handling
"""

import pytest
from core.time_expression_parser import TimeExpressionParser, parse_time_expression, TimeUnit


class TestTimeExpressionParserInit:
    """Tests for TimeExpressionParser initialization."""

    def test_init_default(self):
        """Test default initialization."""
        parser = TimeExpressionParser()
        assert parser is not None


class TestParseTimeExpression:
    """Tests for parse_time_expression function."""

    def test_parse_minutes(self):
        """Test parsing minutes expressions."""
        result = parse_time_expression("5min")
        assert result["value"] == 5
        assert result["unit"] == "minutes"

    def test_parse_minutes_abbrev(self):
        """Test parsing abbreviated minutes."""
        result = parse_time_expression("5m")
        assert result["value"] == 5
        assert result["unit"] == "minutes"

    def test_parse_hours(self):
        """Test parsing hours expressions."""
        result = parse_time_expression("2h")
        assert result["value"] == 2
        assert result["unit"] == "hours"

    def test_parse_hours_abbrev(self):
        """Test parsing abbreviated hours."""
        result = parse_time_expression("2hr")
        assert result["value"] == 2
        assert result["unit"] == "hours"

    def test_parse_days(self):
        """Test parsing days expressions."""
        result = parse_time_expression("3d")
        assert result["value"] == 3
        assert result["unit"] == "days"

    def test_parse_weeks(self):
        """Test parsing weeks expressions."""
        result = parse_time_expression("1w")
        assert result["value"] == 1
        assert result["unit"] == "weeks"

    def test_parse_complex_expression(self):
        """Test parsing complex time expressions."""
        result = parse_time_expression("1h 30min")
        assert result["value"] == 90  # 90 minutes
        assert result["unit"] == "minutes"

    def test_parse_multiple_days(self):
        """Test parsing multiple days."""
        result = parse_time_expression("3d 12h")
        # Should parse and convert to base unit
        assert result["value"] is not None
        assert result["unit"] in ["minutes", "hours", "days"]


class TestTimeExpressionParser:
    """Tests for TimeExpressionParser class methods."""

    def test_validate_expression_valid(self):
        """Test validating valid expressions."""
        parser = TimeExpressionParser()
        assert parser.validate_expression("5min") is True
        assert parser.validate_expression("2h") is True
        assert parser.validate_expression("1d") is True

    def test_validate_expression_invalid(self):
        """Test validating invalid expressions."""
        parser = TimeExpressionParser()
        assert parser.validate_expression("invalid") is False
        assert parser.validate_expression("") is False

    def test_extract_time_unit(self):
        """Test extracting time unit from expression."""
        parser = TimeExpressionParser()

        unit = parser.extract_time_unit("5min")
        assert unit == TimeUnit.MINUTE

        unit = parser.extract_time_unit("2h")
        assert unit == TimeUnit.HOUR

        unit = parser.extract_time_unit("1d")
        assert unit == TimeUnit.DAY

    def test_extract_value(self):
        """Test extracting numeric value from expression."""
        parser = TimeExpressionParser()

        value = parser.extract_value("5min")
        assert value == 5

        value = parser.extract_value("2h")
        assert value == 2

        value = parser.extract_value("1d")
        assert value == 1

    def test_normalize_to_minutes(self):
        """Test normalizing different units to minutes."""
        parser = TimeExpressionParser()

        # 1 hour = 60 minutes
        minutes = parser.normalize_to_minutes(1, TimeUnit.HOUR)
        assert minutes == 60

        # 1 day = 1440 minutes
        minutes = parser.normalize_to_minutes(1, TimeUnit.DAY)
        assert minutes == 1440

        # Minutes stay as minutes
        minutes = parser.normalize_to_minutes(30, TimeUnit.MINUTE)
        assert minutes == 30


class TestTimeUnit:
    """Tests for TimeUnit enum."""

    def test_timeunit_values(self):
        """Test TimeUnit enum values."""
        assert TimeUnit.SECOND.value == "second"
        assert TimeUnit.MINUTE.value == "minute"
        assert TimeUnit.HOUR.value == "hour"
        assert TimeUnit.DAY.value == "day"
        assert TimeUnit.WEEK.value == "week"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_expression(self):
        """Test handling empty expression."""
        with pytest.raises(ValueError):
            parse_time_expression("")

    def test_invalid_unit(self):
        """Test expression with invalid unit."""
        result = parse_time_expression("5x")
        # Should handle gracefully or raise error
        assert result is not None

    def test_zero_value(self):
        """Test zero time value."""
        result = parse_time_expression("0min")
        assert result["value"] == 0

    def test_large_value(self):
        """Test very large time values."""
        result = parse_time_expression("365d")
        assert result["value"] == 365

    def test_whitespace_variations(self):
        """Test expressions with different whitespace."""
        result1 = parse_time_expression("5min")
        result2 = parse_time_expression("5 min")
        result3 = parse_time_expression("5  min")

        # Should handle whitespace variations
        assert result1["value"] == 5


class TestIntegration:
    """Integration tests for time expression parsing."""

    def test_parse_and_calculate_duration(self):
        """Test parsing and calculating total duration."""
        expr1 = parse_time_expression("1h")
        expr2 = parse_time_expression("30min")

        parser = TimeExpressionParser()
        total_minutes = (
            parser.normalize_to_minutes(expr1["value"], TimeUnit.HOUR) +
            parser.normalize_to_minutes(expr2["value"], TimeUnit.MINUTE)
        )

        assert total_minutes == 90  # 60 + 30

    def test_batch_parse_expressions(self):
        """Test parsing multiple expressions."""
        expressions = ["5min", "2h", "1d"]

        results = [parse_time_expression(expr) for expr in expressions]

        assert len(results) == 3
        assert all("value" in r for r in results)
        assert all("unit" in r for r in results)
