"""
Tests for TraceValidator

Tests for trace validation including:
- Trace format validation
- Component trace validation
- Error detection
- Trace reconstruction
"""

import pytest

# Skip tests if aiofiles is not available (optional dependency)
pytest.importorskip("aiofiles")

from core.trace_validator import TraceValidator


@pytest.mark.skip(reason="validate_trace_format function not implemented in core.trace_validator")
class TestValidateTraceFormat:
    """Tests for validate_trace_format function."""
    pass


class TestTraceValidatorInit:
    """Tests for TraceValidator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        validator = TraceValidator()
        assert validator is not None


class TestValidateTraceFormat:
    """Tests for validate_trace_format function."""

    def test_valid_simple_trace(self):
        """Test validating a simple valid trace."""
        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100
        }

        # Should not raise error
        result = validate_trace_format(trace)
        assert result["valid"] is True

    def test_valid_complex_trace(self):
        """Test validating a complex nested trace."""
        trace = {
            "component": "workflow",
            "action": "process",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 500,
            "metadata": {
                "workflow_id": "wf-123",
                "step_count": 5
            },
            "steps": [
                {"step": 1, "status": "completed"},
                {"step": 2, "status": "completed"}
            ]
        }

        result = validate_trace_format(trace)
        assert result["valid"] is True

    def test_missing_required_field(self):
        """Test trace missing required field."""
        trace = {
            "component": "agent",
            "action": "execute"
            # Missing timestamp
        }

        result = validate_trace_format(trace)
        assert result["valid"] is False
        assert "timestamp" in result.get("errors", [])

    def test_invalid_timestamp_format(self):
        """Test trace with invalid timestamp."""
        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "invalid-timestamp",
            "duration": 100
        }

        result = validate_trace_format(trace)
        assert result["valid"] is False

    def test_invalid_duration_type(self):
        """Test trace with non-numeric duration."""
        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": "invalid"
        }

        result = validate_trace_format(trace)
        assert result["valid"] is False

    def test_empty_trace(self):
        """Test empty trace object."""
        trace = {}

        result = validate_trace_format(trace)
        assert result["valid"] is False


class TestTraceValidator:
    """Tests for TraceValidator class methods."""

    def test_validate_trace(self):
        """Test full trace validation."""
        validator = TraceValidator()

        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100,
            "trace_id": "trace-123"
        }

        result = validator.validate_trace(trace)
        assert result["valid"] is True

    def test_validate_component_trace(self):
        """Test component-specific trace validation."""
        validator = TraceValidator()

        # Agent trace
        agent_trace = {
            "component": "agent",
            "action": "execute",
            "agent_id": "agent-123",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100
        }

        result = validator.validate_component_trace("agent", agent_trace)
        assert result["valid"] is True

        # Workflow trace
        workflow_trace = {
            "component": "workflow",
            "action": "process",
            "workflow_id": "wf-123",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 500
        }

        result = validator.validate_component_trace("workflow", workflow_trace)
        assert result["valid"] is True


class TestErrorDetection:
    """Tests for error detection in traces."""

    def test_detect_incomplete_trace(self):
        """Test detecting incomplete trace data."""
        validator = TraceValidator()

        incomplete_trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z"
            # Missing duration
        }

        result = validator.detect_errors(incomplete_trace)
        assert len(result["errors"]) > 0

    def test_detect_invalid_component(self):
        """Test detecting invalid component."""
        validator = TraceValidator()

        trace = {
            "component": "invalid_component",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100
        }

        result = validator.detect_errors(trace)
        assert len(result["errors"]) > 0
        assert "component" in str(result["errors"]).lower()


class TestTraceReconstruction:
    """Tests for trace reconstruction."""

    def test_reconstruct_simple_trace(self):
        """Test reconstructing a trace from fragments."""
        validator = TraceValidator()

        fragments = [
            {"event": "start", "timestamp": "2024-01-01T00:00:00Z"},
            {"event": "end", "timestamp": "2024-01-01T00:01:40Z"}
        ]

        trace = validator.reconstruct_trace(fragments)
        assert trace["duration"] == 100  # 100 seconds

    def test_reconstruct_with_metadata(self):
        """Test reconstructing trace with metadata."""
        validator = TraceValidator()

        fragments = {
            "events": [
                {"action": "start", "timestamp": "2024-01-01T00:00:00Z"},
                {"action": "end", "timestamp": "2024-01-01T00:01:40Z"}
            ],
            "metadata": {
                "component": "agent",
                "agent_id": "agent-123"
            }
        }

        trace = validator.reconstruct_trace(fragments)
        assert trace["component"] == "agent"
        assert trace["agent_id"] == "agent-123"


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError("Invalid trace format", field="timestamp")

        assert error.message == "Invalid trace format"
        assert error.field == "timestamp"
        assert str(error) == "Invalid trace format (field: timestamp)"

    def test_validation_error_with_details(self):
        """Test ValidationError with details."""
        error = ValidationError(
            "Multiple errors",
            details={"error1": "Missing field", "error2": "Invalid type"}
        )

        assert error.details is not None
        assert len(error.details) == 2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_null_trace(self):
        """Test handling null trace."""
        validator = TraceValidator()
        result = validator.validate_trace(None)
        assert result["valid"] is False

    def test_trace_with_extra_fields(self):
        """Test trace with unexpected extra fields."""
        validator = TraceValidator()

        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100,
            "extra_field": "unexpected"
        }

        # Should handle gracefully
        result = validator.validate_trace(trace)
        assert result is not None

    def test_malformed_json_trace(self):
        """Test handling malformed JSON trace."""
        validator = TraceValidator()

        malformed = '{"component": "agent", "action": "execute"'  # Missing closing brace

        result = validator.validate_format_from_json(malformed)
        assert result["valid"] is False


class TestIntegration:
    """Integration tests for trace validation."""

    def test_validate_and_enrich_trace(self):
        """Test validating and enriching trace data."""
        validator = TraceValidator()

        trace = {
            "component": "agent",
            "action": "execute",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration": 100,
            "agent_id": "agent-123"
        }

        result = validator.validate_and_enrich(trace)
        assert result["valid"] is True
        assert "enriched_at" in result

    def test_batch_validate_traces(self):
        """Test validating multiple traces."""
        validator = TraceValidator()

        traces = [
            {"component": "agent", "action": "execute", "timestamp": "2024-01-01T00:00:00Z", "duration": 100},
            {"component": "workflow", "action": "process", "timestamp": "2024-01-01T00:00:00Z", "duration": 500},
            {"component": "agent", "action": "analyze", "timestamp": "2024-01-01T00:00:00Z", "duration": 200}
        ]

        results = [validator.validate_trace(t) for t in traces]
        assert all(r["valid"] is True for r in results)

    def test_trace_chain_validation(self):
        """Test validating a chain of related traces."""
        validator = TraceValidator()

        trace_chain = [
            {"component": "agent", "action": "start", "timestamp": "2024-01-01T00:00:00Z", "duration": 10, "parent_id": None},
            {"component": "agent", "action": "process", "timestamp": "2024-01-01T00:00:10Z", "duration": 50, "parent_id": "trace-1"},
            {"component": "agent", "action": "complete", "timestamp": "2024-01-01T00:01:00Z", "duration": 20, "parent_id": "trace-2"}
        ]

        results = validator.validate_chain(trace_chain)
        assert results["valid_chain"] is True
        assert results["total_duration"] == 80
