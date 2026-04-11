"""
Core Coverage Expansion Tests - Phase 251 Plan 03

Targets core modules with coverage gaps.
Focuses on utility functions and helpers.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


class TestAgentUtilities:
    """Test agent utility functions."""

    def test_generate_agent_id(self):
        """Test agent ID generation."""
        from core.agent_utils import generate_agent_id
        agent_id = generate_agent_id()
        assert agent_id is not None
        assert isinstance(agent_id, str)
        assert len(agent_id) > 0

    def test_parse_maturity_level(self):
        """Test maturity level parsing."""
        from core.agent_utils import parse_maturity_level

        # Valid maturity levels
        assert parse_maturity_level("STUDENT") == "STUDENT"
        assert parse_maturity_level("INTERN") == "INTERN"
        assert parse_maturity_level("SUPERVISED") == "SUPERVISED"
        assert parse_maturity_level("AUTONOMOUS") == "AUTONOMOUS"

        # Invalid defaults to STUDENT
        assert parse_maturity_level("INVALID") == "STUDENT"
        assert parse_maturity_level(None) == "STUDENT"

    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        from core.agent_utils import calculate_confidence_score

        # High success rate -> high confidence
        assert calculate_confidence_score(10, 0) > 0.8
        # Low success rate -> low confidence
        assert calculate_confidence_score(0, 10) < 0.2


class TestWorkflowUtilities:
    """Test workflow utility functions."""

    def test_validate_workflow_definition(self):
        """Test workflow definition validation."""
        from core.workflow_utils import validate_workflow_definition

        # Valid workflow
        valid_workflow = {
            "name": "test_workflow",
            "steps": [
                {"name": "step1", "action": "test"}
            ]
        }
        assert validate_workflow_definition(valid_workflow) is True

        # Invalid workflow (missing steps)
        invalid_workflow = {
            "name": "test_workflow"
        }
        assert validate_workflow_definition(invalid_workflow) is False

    def test_workflow_status_transitions(self):
        """Test workflow status transitions."""
        from core.workflow_utils import can_transition_status

        # Valid transitions
        assert can_transition_status("pending", "running") is True
        assert can_transition_status("running", "completed") is True
        assert can_transition_status("running", "failed") is True

        # Invalid transitions
        assert can_transition_status("completed", "running") is False
        assert can_transition_status("failed", "pending") is False


class TestEpisodeUtilities:
    """Test episode utility functions."""

    def test_segment_by_time_gap(self):
        """Test episode segmentation by time gap."""
        from core.episode_utils import segment_by_time_gap

        events = [
            {"timestamp": datetime(2026, 1, 1, 10, 0, 0), "content": "A"},
            {"timestamp": datetime(2026, 1, 1, 10, 0, 10), "content": "B"},
            # 5 minute gap - should segment here
            {"timestamp": datetime(2026, 1, 1, 10, 5, 10), "content": "C"},
        ]

        segments = segment_by_time_gap(events, gap_minutes=2)
        assert len(segments) == 2
        assert len(segments[0]) == 2
        assert len(segments[1]) == 1

    def test_calculate_episode_summary(self):
        """Test episode summary calculation."""
        from core.episode_utils import calculate_episode_summary

        events = [
            {"content": "User asked about sales data"},
            {"content": "Agent retrieved sales report"},
            {"content": "Agent displayed chart"}
        ]

        summary = calculate_episode_summary(events)
        assert summary is not None
        assert len(summary) > 0
        assert "sales" in summary.lower()


class TestValidationUtilities:
    """Test validation utility functions."""

    def test_validate_email(self):
        """Test email validation."""
        from core.validation_utils import validate_email

        # Valid emails
        assert validate_email("test@example.com") is True
        assert validate_email("user.name+tag@example.co.uk") is True

        # Invalid emails
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False

    def test_validate_url(self):
        """Test URL validation."""
        from core.validation_utils import validate_url

        # Valid URLs
        assert validate_url("https://example.com") is True
        assert validate_url("http://example.com/path") is True

        # Invalid URLs
        assert validate_url("not-a-url") is False
        assert validate_url("example.com") is False


class TestTimeUtilities:
    """Test time utility functions."""

    def test_parse_iso_timestamp(self):
        """Test ISO timestamp parsing."""
        from core.time_utils import parse_iso_timestamp

        # Valid ISO timestamps
        ts = parse_iso_timestamp("2026-04-11T10:00:00Z")
        assert ts is not None
        assert isinstance(ts, datetime)

        # Invalid timestamps
        assert parse_iso_timestamp("invalid") is None
        assert parse_iso_timestamp("") is None

    def test_format_duration(self):
        """Test duration formatting."""
        from core.time_utils import format_duration

        # Test various durations
        assert format_duration(60) == "1m 0s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(0) == "0s"


class TestStringUtilities:
    """Test string utility functions."""

    def test_sanitize_string(self):
        """Test string sanitization."""
        from core.string_utils import sanitize_string

        # Remove HTML tags
        assert sanitize_string("<p>Hello</p>") == "Hello"
        assert sanitize_string("<script>alert('xss')</script>Test") == "Test"

    def test_truncate_string(self):
        """Test string truncation."""
        from core.string_utils import truncate_string

        # Truncate long strings
        long_string = "a" * 100
        truncated = truncate_string(long_string, max_length=50)
        assert len(truncated) <= 50
        assert truncated.endswith("...")

        # Don't truncate short strings
        short_string = "hello"
        assert truncate_string(short_string, max_length=50) == short_string


class TestJsonUtilities:
    """Test JSON utility functions."""

    def test_safe_json_parse(self):
        """Test safe JSON parsing."""
        from core.json_utils import safe_json_parse

        # Valid JSON
        result = safe_json_parse('{"key": "value"}')
        assert result == {"key": "value"}

        # Invalid JSON
        assert safe_json_parse("invalid") is None
        assert safe_json_parse("") is None

    def test_safe_json_dumps(self):
        """Test safe JSON serialization."""
        from core.json_utils import safe_json_dumps

        # Valid objects
        result = safe_json_dumps({"key": "value"})
        assert result == '{"key": "value"}'

        # Invalid objects (non-serializable)
        assert safe_json_dumps(datetime(2026, 1, 1)) is not None
        assert isinstance(safe_json_dumps(datetime(2026, 1, 1)), str)
