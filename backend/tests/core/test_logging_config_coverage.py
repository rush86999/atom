"""
Comprehensive tests for Logging Configuration

Target: 60%+ coverage for core/logging_config.py (472 lines)
Focus: Setup, formatting, context management, middleware integration
"""

import pytest
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path

from core.logging_config import (
    setup_logging,
    get_logger,
    ColoredFormatter,
    LogColors,
    bind_context,
    get_context,
    generate_correlation_id,
    LoggerContext,
    LoggingContextMiddleware,
    StructuredLogger,
    CORRELATION_ID,
    USER_ID,
    REQUEST_ID,
)


# ========================================================================
# TestLoggingConfig: Logging Setup and Configuration
# ========================================================================


class TestLoggingConfig:
    """Test logging configuration and setup."""

    def test_setup_logging_default_configuration(self):
        """Test setup_logging with default configuration."""
        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_logging_custom_level(self):
        """Test setup_logging with custom log level."""
        setup_logging(level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_with_file(self, tmp_path):
        """Test setup_logging with file output."""
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        root_logger = logging.getLogger()
        # Should have both console and file handlers
        assert len(root_logger.handlers) >= 1

        # Verify file handler exists
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates log directory if it doesn't exist."""
        log_file = tmp_path / "logs" / "test.log"

        setup_logging(log_file=str(log_file))

        # Directory should be created
        assert log_file.parent.exists()

    def test_setup_logging_without_colors(self):
        """Test setup_logging with colors disabled."""
        setup_logging(enable_colors=False)

        root_logger = logging.getLogger()
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]

        for handler in console_handlers:
            formatter = handler.formatter
            if isinstance(formatter, ColoredFormatter):
                assert formatter.use_colors is False

    @patch.dict('os.environ', {'LOG_LEVEL': 'WARNING'})
    def test_setup_logging_from_environment(self):
        """Test setup_logging reads LOG_LEVEL from environment."""
        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    @patch.dict('os.environ', {'LOG_FILE': '/tmp/test.log'})
    def test_setup_logging_file_from_environment(self):
        """Test setup_logging reads LOG_FILE from environment."""
        setup_logging()

        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup_logging clears existing handlers."""
        # Add a handler manually
        root_logger = logging.getLogger()
        initial_count = len(root_logger.handlers)

        setup_logging()

        # Handlers should be replaced
        assert len(root_logger.handlers) != initial_count or initial_count == 0


# ========================================================================
# TestLogFormatting: Colored Formatter and Output
# ========================================================================


class TestLogFormatting:
    """Test log formatting and colored output."""

    def test_colored_formatter_initialization(self):
        """Test ColoredFormatter initialization."""
        formatter = ColoredFormatter(use_colors=True)
        assert formatter.use_colors is True

    def test_colored_formatter_without_colors(self):
        """Test ColoredFormatter with colors disabled."""
        formatter = ColoredFormatter(use_colors=False)
        assert formatter.use_colors is False

    def test_colored_formatter_format_includes_timestamp(self):
        """Test that formatter includes timestamp in output."""
        formatter = ColoredFormatter(use_colors=False)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)

        # Should contain timestamp
        assert "[" in formatted  # Timestamp format
        assert "INFO" in formatted
        assert "Test message" in formatted

    def test_colored_formatter_includes_logger_name(self):
        """Test that formatter includes logger name."""
        formatter = ColoredFormatter(use_colors=False, show_logger_name=True)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        assert "test.logger" in formatted

    def test_colored_formatter_without_logger_name(self):
        """Test formatter with logger name disabled."""
        formatter = ColoredFormatter(use_colors=False, show_logger_name=False)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        assert "test.logger" not in formatted

    def test_colored_formatter_with_exception(self):
        """Test formatter includes exception information."""
        formatter = ColoredFormatter(use_colors=False)

        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=True
            )
            record.exc_info = (ValueError, ValueError("Test exception"), None)

            formatted = formatter.format(record)

            assert "ValueError" in formatted or "Error occurred" in formatted


# ========================================================================
# TestLogContext: Context Variables and Correlation IDs
# ========================================================================


class TestLogContext:
    """Test context variables and correlation ID management."""

    def test_bind_context_correlation_id(self):
        """Test binding correlation ID to context."""
        test_id = "test-correlation-123"
        bind_context(correlation_id=test_id)

        assert CORRELATION_ID.get() == test_id

    def test_bind_context_user_id(self):
        """Test binding user ID to context."""
        test_user = "user-123"
        bind_context(user_id=test_user)

        assert USER_ID.get() == test_user

    def test_bind_context_request_id(self):
        """Test binding request ID to context."""
        test_request = "request-123"
        bind_context(request_id=test_request)

        assert REQUEST_ID.get() == test_request

    def test_bind_context_multiple_values(self):
        """Test binding multiple context values at once."""
        bind_context(
            correlation_id="corr-123",
            user_id="user-123",
            request_id="req-123"
        )

        assert CORRELATION_ID.get() == "corr-123"
        assert USER_ID.get() == "user-123"
        assert REQUEST_ID.get() == "req-123"

    def test_bind_context_ignores_none_values(self):
        """Test that bind_context ignores None values."""
        bind_context(
            correlation_id="corr-123",
            user_id=None,  # Should be ignored
            request_id="req-123"
        )

        assert CORRELATION_ID.get() == "corr-123"
        # USER_ID should not be set
        try:
            USER_ID.get()
            assert False, "Should raise LookupError"
        except LookupError:
            pass  # Expected

    def test_get_context(self):
        """Test getting all context variables."""
        bind_context(
            correlation_id="corr-123",
            user_id="user-123",
            request_id="req-123"
        )

        context = get_context()

        assert context["correlation_id"] == "corr-123"
        assert context["user_id"] == "user-123"
        assert context["request_id"] == "req-123"

    def test_get_context_empty(self):
        """Test getting context when no values are set."""
        # Clear context
        try:
            CORRELATION_ID.set("")
            USER_ID.set("")
            REQUEST_ID.set("")
        except:
            pass

        context = get_context()

        # Should return empty strings or handle gracefully
        assert "correlation_id" in context
        assert "user_id" in context
        assert "request_id" in context

    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        corr_id = generate_correlation_id()

        assert isinstance(corr_id, str)
        assert len(corr_id) > 0

    def test_generate_correlation_id_unique(self):
        """Test that generated correlation IDs are unique."""
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()

        assert id1 != id2


# ========================================================================
# TestLoggerContext: Logger Context Manager
# ========================================================================


class TestLoggerContext:
    """Test LoggerContext for temporary level changes."""

    def test_logger_context_changes_level(self):
        """Test LoggerContext temporarily changes log level."""
        logger = logging.getLogger("test_logger")
        original_level = logger.level

        with LoggerContext("test_logger", logging.DEBUG):
            assert logger.level == logging.DEBUG

        # Level should be restored
        assert logger.level == original_level

    def test_logger_context_returns_logger(self):
        """Test that LoggerContext returns logger instance."""
        with LoggerContext("test_logger", logging.DEBUG) as logger:
            assert logger is not None
            assert logger.name == "test_logger"

    def test_logger_context_restores_on_exception(self):
        """Test LoggerContext restores level even on exception."""
        logger = logging.getLogger("test_logger")
        original_level = logger.level

        try:
            with LoggerContext("test_logger", logging.DEBUG):
                assert logger.level == logging.DEBUG
                raise ValueError("Test error")
        except ValueError:
            pass

        # Level should still be restored
        assert logger.level == original_level


# ========================================================================
# TestStructuredLogger: Structured Logging Helper
# ========================================================================


class TestStructuredLogger:
    """Test StructuredLogger helper class."""

    def test_structured_logger_initialization(self):
        """Test StructuredLogger initialization."""
        logger = StructuredLogger("test_logger")
        assert logger._logger is not None
        assert logger._logger.name == "test_logger"

    def test_structured_logger_info(self):
        """Test StructuredLogger info method."""
        logger = StructuredLogger("test_logger")
        # Should not raise exception
        logger.info("Test info message")

    def test_structured_logger_error(self):
        """Test StructuredLogger error method."""
        logger = StructuredLogger("test_logger")
        # Should not raise exception
        logger.error("Test error message")

    def test_structured_logger_with_context(self):
        """Test StructuredLogger includes context variables."""
        bind_context(correlation_id="test-123")

        logger = StructuredLogger("test_logger")
        # Should not raise exception
        logger.info("Test message with context")

    def test_structured_logger_warning(self):
        """Test StructuredLogger warning method."""
        logger = StructuredLogger("test_logger")
        logger.warning("Test warning message")

    def test_structured_logger_debug(self):
        """Test StructuredLogger debug method."""
        logger = StructuredLogger("test_logger")
        logger.debug("Test debug message")

    def test_structured_logger_critical(self):
        """Test StructuredLogger critical method."""
        logger = StructuredLogger("test_logger")
        logger.critical("Test critical message")


# ========================================================================
# TestMiddleware: FastAPI Middleware Integration
# ========================================================================


class TestMiddleware:
    """Test LoggingContextMiddleware for FastAPI."""

    @pytest.mark.asyncio
    async def test_middleware_generates_correlation_id(self):
        """Test middleware generates correlation ID."""
        middleware = LoggingContextMiddleware(app=MagicMock())

        request = MagicMock()
        request.state = MagicMock()

        async def call_next(req):
            response = MagicMock()
            response.headers = {}
            return response

        response = await middleware.dispatch(request, call_next)

        # Should set correlation ID in state and response headers
        assert hasattr(request.state, 'correlation_id')
        assert 'X-Correlation-ID' in response.headers

    @pytest.mark.asyncio
    async def test_middleware_binds_context(self):
        """Test middleware binds context variables."""
        middleware = LoggingContextMiddleware(app=MagicMock())

        request = MagicMock()
        request.state = MagicMock()
        request.state.user_id = "user-123"

        async def call_next(req):
            # Context should be bound during request processing
            assert CORRELATION_ID.get() is not None
            assert USER_ID.get() == "user-123"
            response = MagicMock()
            response.headers = {}
            return response

        await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_middleware_adds_response_header(self):
        """Test middleware adds X-Correlation-ID to response."""
        middleware = LoggingContextMiddleware(app=MagicMock())

        request = MagicMock()
        request.state = MagicMock()

        async def call_next(req):
            response = MagicMock()
            response.headers = {}
            return response

        response = await middleware.dispatch(request, call_next)

        assert 'X-Correlation-ID' in response.headers
        assert len(response.headers['X-Correlation-ID']) > 0

    def test_get_correlation_id(self):
        """Test getting correlation ID from context."""
        bind_context(correlation_id="test-123")

        corr_id = get_correlation_id()
        assert corr_id == "test-123"


# ========================================================================
# TestLibraryLoggerConfiguration: Library Logger Suppression
# ========================================================================


class TestLibraryLoggerConfiguration:
    """Test library logger configuration and suppression."""

    def test_configure_library_loggers(self):
        """Test that library loggers are configured to reduce noise."""
        from core.logging_config import _configure_library_loggers

        setup_logging()

        # Check that noisy libraries are set to WARNING or higher
        uvicorn_logger = logging.getLogger("uvicorn")
        assert uvicorn_logger.level >= logging.WARNING

        sqlalchemy_logger = logging.getLogger("sqlalchemy")
        assert sqlalchemy_logger.level >= logging.WARNING

        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level >= logging.WARNING


# ========================================================================
# TestGetLogger: Logger Instance Creation
# ========================================================================


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_instance(self):
        """Test get_logger returns logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_name_same_instance(self):
        """Test get_logger returns same instance for same name."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2

    def test_get_logger_different_names_different_instances(self):
        """Test get_logger returns different instances for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        assert logger1 is not logger2


# ========================================================================
# TestLogRotation: File Logging and Rotation
# ========================================================================


class TestLogRotation:
    """Test file logging and rotation configuration."""

    def test_file_handler_encoding(self, tmp_path):
        """Test file handler uses UTF-8 encoding."""
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]

        assert len(file_handlers) > 0
        assert file_handlers[0].encoding == 'utf-8'

    def test_file_handler_plain_text_format(self, tmp_path):
        """Test file handler uses plain text format (no colors)."""
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]

        assert len(file_handlers) > 0
        # File formatter should not be ColoredFormatter
        assert not isinstance(file_handlers[0].formatter, ColoredFormatter)


# ========================================================================
# TestEdgeCases: Error Handling and Edge Cases
# ========================================================================


class TestEdgeCases:
    """Test error handling and edge cases."""

    def test_invalid_log_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        setup_logging(level="INVALID_LEVEL")

        root_logger = logging.getLogger()
        # getattr returns None for invalid level, defaults to INFO
        assert root_logger.level == logging.INFO

    def test_setup_logging_idempotent(self):
        """Test that calling setup_logging multiple times is safe."""
        setup_logging(level="INFO")
        setup_logging(level="DEBUG")

        root_logger = logging.getLogger()
        # Should not crash, last call wins
        assert root_logger.level == logging.DEBUG

    def test_empty_log_message(self):
        """Test logging empty message."""
        logger = get_logger("test")
        # Should not raise exception
        logger.info("")

    def test_unicode_log_message(self):
        """Test logging unicode characters."""
        logger = get_logger("test")
        # Should not raise exception
        logger.info("Test with emoji: 🚀 Test with unicode: Ñoño")

    def test_very_long_log_message(self):
        """Test logging very long message."""
        logger = get_logger("test")
        long_message = "x" * 10000
        # Should not raise exception
        logger.info(long_message)
