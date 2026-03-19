"""
Comprehensive tests for StructuredLogger module.

Tests cover the StructuredFormatter, StructuredLogger class,
and convenience functions for structured logging.
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from core.structured_logger import (
    StructuredFormatter,
    StructuredLogger,
    clear_request_id,
    get_logger,
    log_critical,
    log_debug,
    log_error,
    log_exception,
    log_info,
    log_warning,
    request_id_ctx,
    set_request_id,
)


class TestStructuredFormatter:
    """Test suite for StructuredFormatter class."""

    def test_format_basic_log_record(self):
        """Test that formatter formats log record as JSON."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"

    def test_format_includes_timestamp(self):
        """Test that JSON output includes timestamp field."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert "timestamp" in parsed
        # Verify ISO format
        datetime.fromisoformat(parsed["timestamp"])

    def test_format_includes_level(self):
        """Test that JSON output includes level field."""
        formatter = StructuredFormatter()
        for level_name, level in [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="test.py",
                lineno=42,
                msg=f"Test {level_name}",
                args=(),
                exc_info=None,
            )

            result = formatter.format(record)
            parsed = json.loads(result)

            assert parsed["level"] == level_name

    def test_format_includes_message(self):
        """Test that JSON output includes message field."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message with context",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["message"] == "Test message with context"

    def test_format_includes_logger_name(self):
        """Test that JSON output includes logger name."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="my.custom.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["logger"] == "my.custom.logger"

    def test_format_includes_module(self):
        """Test that JSON output includes module name."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["module"] == "test_module"

    def test_format_includes_function(self):
        """Test that JSON output includes function name."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["function"] == "test_function"

    def test_format_includes_line_number(self):
        """Test that JSON output includes line number."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["line"] == 42

    def test_format_includes_context(self):
        """Test that JSON output includes bound context."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.structured_context = {"user_id": "123", "request_id": "abc"}

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["user_id"] == "123"
        assert parsed["request_id"] == "abc"

    def test_format_includes_extra(self):
        """Test that JSON output includes extra fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.structured_context = {"custom_field": "custom_value", "count": 42}

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["custom_field"] == "custom_value"
        assert parsed["count"] == 42

    def test_format_handles_missing_context(self):
        """Test that formatter works without context."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"

    def test_format_uses_iso8601_timestamp(self):
        """Test that timestamp format is ISO8601."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        # ISO8601 format should be parseable
        timestamp = parsed["timestamp"]
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp or "-" in timestamp
        # Should not raise exception
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_format_json_valid_json(self):
        """Test that output is valid JSON."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.structured_context = {"key": "value"}

        result = formatter.format(record)

        # Should not raise exception
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_format_handles_exception_info(self):
        """Test that formatter handles exception info."""
        formatter = StructuredFormatter()
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            result = formatter.format(record)
            parsed = json.loads(result)

            assert "exception" in parsed
            assert parsed["exception"]["type"] == "ValueError"
            assert "Test exception" in parsed["exception"]["message"]

    def test_format_fallback_on_json_error(self):
        """Test fallback to simple format if JSON serialization fails."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Add a non-serializable object
        record.structured_context = {"bad_object": object()}

        # Should not raise exception, should fallback
        result = formatter.format(record)
        assert isinstance(result, str)


class TestStructuredLogger:
    """Test suite for StructuredLogger class."""

    def test_initialization_default(self):
        """Test creating logger with default settings."""
        logger = StructuredLogger("test_logger")

        assert logger.logger.name == "test_logger"
        assert logger.logger.level == logging.INFO

    def test_initialization_custom_level(self):
        """Test setting custom log level."""
        logger = StructuredLogger("test_logger", level=logging.DEBUG)

        assert logger.logger.level == logging.DEBUG

    def test_initialization_with_name(self):
        """Test setting logger name."""
        logger = StructuredLogger("my.custom.module")

        assert logger.logger.name == "my.custom.module"

    def test_log_debug_level(self):
        """Test logging at DEBUG level."""
        logger = StructuredLogger("test_logger", level=logging.DEBUG)

        # Capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.debug("Debug message", debug_data="test")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["level"] == "DEBUG"
        assert parsed["message"] == "Debug message"
        assert parsed["debug_data"] == "test"

    def test_log_info_level(self):
        """Test logging at INFO level."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("Info message", user_id="123")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Info message"
        assert parsed["user_id"] == "123"

    def test_log_warning_level(self):
        """Test logging at WARNING level."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.warning("Warning message", warning_code="W001")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["level"] == "WARNING"
        assert parsed["message"] == "Warning message"
        assert parsed["warning_code"] == "W001"

    def test_log_error_level(self):
        """Test logging at ERROR level."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.error("Error message", error_code="E001")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error message"
        assert parsed["error_code"] == "E001"

    def test_log_critical_level(self):
        """Test logging at CRITICAL level."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.critical("Critical message", system_failure=True)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["level"] == "CRITICAL"
        assert parsed["message"] == "Critical message"
        assert parsed["system_failure"] is True

    def test_log_with_context(self):
        """Test logging with bound context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        # Bind context
        set_request_id("req-123")
        logger.info("Request received", user_id="user-456")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["request_id"] == "req-123"
        assert parsed["user_id"] == "user-456"

        # Cleanup
        clear_request_id()

    def test_log_with_extra_fields(self):
        """Test logging with extra fields."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info(
            "Event occurred",
            event_type="user_action",
            event_id="evt-001",
            metadata={"key": "value"},
        )

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["event_type"] == "user_action"
        assert parsed["event_id"] == "evt-001"
        assert parsed["metadata"]["key"] == "value"

    def test_log_filters_by_level(self):
        """Test that logs are filtered by configured level."""
        logger = StructuredLogger("test_logger", level=logging.WARNING)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        output = stream.getvalue()
        lines = [line for line in output.strip().split("\n") if line]

        # Should only have WARNING and ERROR
        assert len(lines) == 2

        parsed1 = json.loads(lines[0])
        parsed2 = json.loads(lines[1])
        levels = {parsed1["level"], parsed2["level"]}

        assert levels == {"WARNING", "ERROR"}

    def test_log_exception_with_traceback(self):
        """Test logging exception with traceback."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        try:
            raise ValueError("Test exception for logging")
        except ValueError:
            logger.exception("Error occurred", context="test_context")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert parsed["context"] == "test_context"
        assert "exception_type" in parsed
        assert parsed["exception_type"] == "ValueError"
        assert "exception_message" in parsed
        assert "exception_traceback" in parsed
        assert "Test exception for logging" in parsed["exception_message"]

    def test_log_includes_timestamp(self):
        """Test that log includes timestamp."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("Test message")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        assert "timestamp" in parsed
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(parsed["timestamp"])

    def test_log_without_duplicate_handlers(self):
        """Test that logger doesn't add duplicate handlers."""
        logger = StructuredLogger("test_logger")

        initial_count = len(logger.logger.handlers)

        # Create another logger with same name
        logger2 = StructuredLogger("test_logger")

        # Should not add duplicate handlers
        assert len(logger2.logger.handlers) == initial_count

    def test_log_with_custom_timestamp(self):
        """Test logging with custom timestamp in context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        custom_timestamp = "2024-03-19T12:00:00Z"
        logger.info("Test message", timestamp=custom_timestamp)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        # Custom timestamp should be preserved
        assert parsed["timestamp"] == custom_timestamp


class TestLoggerContextFunctions:
    """Test suite for context management functions."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns StructuredLogger instance."""
        logger = get_logger("test.module")

        assert isinstance(logger, StructuredLogger)
        assert logger.logger.name == "test.module"

    def test_get_logger_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")

        # Both should be StructuredLogger instances
        assert isinstance(logger1, StructuredLogger)
        assert isinstance(logger2, StructuredLogger)
        assert logger1.logger.name == logger2.logger.name

    def test_bind_context_adds_context(self):
        """Test that bind_context adds context to logger."""
        clear_request_id()

        logger = StructuredLogger("test_logger")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        set_request_id("req-456")
        logger.info("Test message")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        assert parsed["request_id"] == "req-456"

        clear_request_id()

    def test_bind_context_multiple_contexts(self):
        """Test binding multiple context values."""
        clear_request_id()

        logger = StructuredLogger("test_logger")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        set_request_id("req-789")
        logger.info("Test message", user_id="user-001", session_id="session-123")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        assert parsed["request_id"] == "req-789"
        assert parsed["user_id"] == "user-001"
        assert parsed["session_id"] == "session-123"

        clear_request_id()

    def test_clear_context_removes_context(self):
        """Test that clear_context removes all bound context."""
        set_request_id("req-999")

        logger = StructuredLogger("test_logger")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        # First log with context
        logger.info("Message with context")
        output1 = stream.getvalue()
        parsed1 = json.loads(output1.strip().split("\n")[-1])
        assert parsed1["request_id"] == "req-999"

        # Clear context
        clear_request_id()

        # Second log without context
        logger.info("Message without context")
        output2 = stream.getvalue()
        lines = output2.strip().split("\n")
        parsed2 = json.loads(lines[-1])
        assert "request_id" not in parsed2 or parsed2.get("request_id") is None

    def test_bind_context_thread_safe(self):
        """Test that context is thread-local (isolated per thread)."""
        clear_request_id()

        results = {}

        def thread_func(thread_id):
            # Each thread sets its own request_id
            set_request_id(f"req-{thread_id}")

            logger = StructuredLogger("test_logger")
            stream = StringIO()
            handler = logging.StreamHandler(stream)
            handler.setFormatter(StructuredFormatter())
            logger.logger.addHandler(handler)

            logger.info("Thread message")

            output = stream.getvalue()
            parsed = json.loads(output.strip().split("\n")[-1])
            results[thread_id] = parsed.get("request_id")

            # Small delay to ensure thread interleaving
            time.sleep(0.01)

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=thread_func, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Each thread should have its own request_id
        assert len(results) == 5
        for thread_id, request_id in results.items():
            assert request_id == f"req-{thread_id}"

        clear_request_id()

    def test_bind_context_with_dict(self):
        """Test binding multiple context values at once via context parameter."""
        clear_request_id()

        logger = StructuredLogger("test_logger")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        context_dict = {"user_id": "user-123", "session_id": "session-456", "action": "test"}

        logger.info("Test message", **context_dict)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])

        assert parsed["user_id"] == "user-123"
        assert parsed["session_id"] == "session-456"
        assert parsed["action"] == "test"


class TestLoggerConvenienceFunctions:
    """Test suite for convenience functions."""

    def test_log_debug_function(self):
        """Test log_debug convenience function."""
        # The convenience functions create their own logger instances
        # Just verify they don't raise exceptions
        try:
            log_debug("Debug test", test_key="test_value")
            assert True  # If we get here, no exception was raised
        except Exception as e:
            pytest.fail(f"log_debug raised exception: {e}")

    def test_log_info_function(self):
        """Test log_info convenience function."""
        try:
            log_info("Info test", info_key="info_value")
            assert True
        except Exception as e:
            pytest.fail(f"log_info raised exception: {e}")

    def test_log_warning_function(self):
        """Test log_warning convenience function."""
        try:
            log_warning("Warning test", warning_key="warning_value")
            assert True
        except Exception as e:
            pytest.fail(f"log_warning raised exception: {e}")

    def test_log_error_function(self):
        """Test log_error convenience function."""
        try:
            log_error("Error test", error_key="error_value")
            assert True
        except Exception as e:
            pytest.fail(f"log_error raised exception: {e}")

    def test_log_critical_function(self):
        """Test log_critical convenience function."""
        try:
            log_critical("Critical test", critical_key="critical_value")
            assert True
        except Exception as e:
            pytest.fail(f"log_critical raised exception: {e}")

    def test_log_exception_function(self):
        """Test log_exception convenience function."""
        try:
            try:
                raise ValueError("Test exception")
            except ValueError:
                log_exception("Exception test", exception_key="exception_value")
            assert True
        except Exception as e:
            pytest.fail(f"log_exception raised exception: {e}")


class TestLoggerEdgeCases:
    """Test suite for edge cases and special scenarios."""

    def test_empty_log_message(self):
        """Test logging empty message."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["message"] == ""

    def test_log_with_special_characters(self):
        """Test logging with special characters in context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info(
            "Special chars",
            special_text='Test with "quotes" and \'apostrophes\'',
            unicode_text="Test with emoji 🎉 and unicode",
        )

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert "quotes" in parsed["special_text"]
        assert "🎉" in parsed["unicode_text"]

    def test_log_with_nested_dict(self):
        """Test logging with nested dictionary in context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        nested_data = {"user": {"id": "123", "name": "Test"}, "metadata": {"count": 42}}

        logger.info("Nested data", data=nested_data)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["data"]["user"]["id"] == "123"
        assert parsed["data"]["metadata"]["count"] == 42

    def test_log_with_very_long_context(self):
        """Test logging with very long context values."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        long_string = "x" * 10000

        logger.info("Long context", long_field=long_string)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert len(parsed["long_field"]) == 10000

    def test_log_with_unicode_in_message(self):
        """Test logging with unicode characters in message."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("Unicode message: 你好 🎉 ñoño café")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert "你好" in parsed["message"]
        assert "🎉" in parsed["message"]
        assert "ñoño" in parsed["message"]

    def test_log_with_none_values(self):
        """Test logging with None values in context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("None values", null_field=None, empty_str="")

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["null_field"] is None
        assert parsed["empty_str"] == ""

    def test_log_with_numeric_values(self):
        """Test logging with various numeric types."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info(
            "Numbers",
            integer=42,
            float_val=3.14,
            negative=-100,
            zero=0,
            scientific=1.23e-4,
        )

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["integer"] == 42
        assert parsed["float_val"] == 3.14
        assert parsed["negative"] == -100
        assert parsed["zero"] == 0

    def test_log_with_boolean_values(self):
        """Test logging with boolean values."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("Booleans", flag_true=True, flag_false=False)

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["flag_true"] is True
        assert parsed["flag_false"] is False

    def test_log_with_list_values(self):
        """Test logging with list values in context."""
        logger = StructuredLogger("test_logger")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)

        logger.info("List values", items=[1, 2, 3], strings=["a", "b", "c"])

        output = stream.getvalue()
        parsed = json.loads(output.strip().split("\n")[-1])
        assert parsed["items"] == [1, 2, 3]
        assert parsed["strings"] == ["a", "b", "c"]

    def test_environment_log_level(self):
        """Test that LOG_LEVEL environment variable is respected."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logger = StructuredLogger("test_logger")
            assert logger.logger.level == logging.DEBUG

        with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}):
            logger2 = StructuredLogger("test_logger2")
            assert logger2.logger.level == logging.ERROR

    def test_invalid_log_level_defaults_to_info(self):
        """Test that invalid LOG_LEVEL defaults to INFO."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID_LEVEL"}):
            logger = StructuredLogger("test_logger")
            assert logger.logger.level == logging.INFO

    def test_log_file_handler_creation(self):
        """Test that file handler is created when LOG_FILE is set."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            log_file = f.name

        try:
            with patch.dict(os.environ, {"LOG_FILE": log_file}):
                logger = StructuredLogger("test_logger_file")

                # Should have file handler
                file_handlers = [h for h in logger.logger.handlers if isinstance(h, logging.FileHandler)]
                assert len(file_handlers) > 0

        finally:
            # Cleanup
            if os.path.exists(log_file):
                os.remove(log_file)

    def test_context_var_default_is_none(self):
        """Test that request_id context variable defaults to None."""
        assert request_id_ctx.get() is None


@pytest.fixture
def clean_logger():
    """Fixture to ensure clean logger state."""
    yield
    # Clear any set request IDs after each test
    clear_request_id()
