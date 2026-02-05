"""
Structured Logger for Atom Platform

Provides consistent, structured logging with contextual information
across all services and API routes.
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable for request ID (persists across async calls)
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredLogger:
    """
    Structured logger with consistent format and contextual information.

    Provides a standardized logging interface that automatically includes
    request IDs, timestamps, and other contextual information.

    Example:
        logger = StructuredLogger(__name__)

        # Basic logging
        logger.info("Agent execution started", agent_id="agent-123")

        # With error details
        logger.error(
            "Database connection failed",
            error_code="DB_001",
            retry_attempt=3,
            exception=str(e)
        )

        # With request context
        logger.info(
            "API request received",
            endpoint="/api/agent/execute",
            method="POST",
            user_id="user-456"
        )
    """

    def __init__(self, name: str, level: Optional[int] = None):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically __name__ of the calling module)
            level: Optional log level (defaults to LOG_LEVEL env var or INFO)
        """
        self.logger = logging.getLogger(name)

        # Set log level from environment or parameter
        if level is None:
            env_level = os.getenv("LOG_LEVEL", "INFO").upper()
            level = getattr(logging, env_level, logging.INFO)

        self.logger.setLevel(level)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        """Configure console and file handlers with structured formatting."""
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.logger.level)

        # Structured formatter
        formatter = StructuredFormatter()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

        # Optional: File handler for production
        log_file = os.getenv("LOG_FILE")
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log(
        self,
        level: int,
        message: str,
        **context
    ):
        """
        Internal logging method with structured context.

        Args:
            level: Log level (logging.INFO, logging.ERROR, etc.)
            message: Log message
            **context: Additional contextual information
        """
        # Add request ID if available
        request_id = request_id_ctx.get()
        if request_id:
            context['request_id'] = request_id

        # Add timestamp if not provided
        if 'timestamp' not in context:
            context['timestamp'] = datetime.utcnow().isoformat()

        # Add logger name
        context['logger'] = self.logger.name

        # Log with structured extra data
        self.logger.log(level, message, extra={'structured_context': context})

    def debug(self, message: str, **context):
        """Log debug message with structured context."""
        self._log(logging.DEBUG, message, **context)

    def info(self, message: str, **context):
        """Log info message with structured context."""
        self._log(logging.INFO, message, **context)

    def warning(self, message: str, **context):
        """Log warning message with structured context."""
        self._log(logging.WARNING, message, **context)

    def error(self, message: str, **context):
        """Log error message with structured context."""
        self._log(logging.ERROR, message, **context)

    def critical(self, message: str, **context):
        """Log critical message with structured context."""
        self._log(logging.CRITICAL, message, **context)

    def exception(self, message: str, **context):
        """
        Log exception with traceback.

        Args:
            message: Error message
            **context: Additional contextual information
        """
        # Add exception info to context
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type:
            context['exception_type'] = exc_type.__name__
            context['exception_message'] = str(exc_value)
            context['exception_traceback'] = ''.join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )

        self._log(logging.ERROR, message, **context)


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured log output.

    Outputs logs in JSON-like format for easy parsing and analysis.
    """

    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Get structured context if available
        structured_context = getattr(record, 'structured_context', {})

        # Build log entry
        log_entry = {
            'level': record.levelname,
            'message': record.getMessage(),
            'timestamp': datetime.utcnow().isoformat(),
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add structured context
        log_entry.update(structured_context)

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

        # Format as JSON string
        import json
        try:
            return json.dumps(log_entry, default=str)
        except Exception:
            # Fallback to simple format if JSON serialization fails
            return f"{record.levelname} - {record.getMessage()}"


def set_request_id(request_id: str):
    """
    Set request ID in context for logging.

    Args:
        request_id: Request identifier

    Example:
        set_request_id("req-123")
        # All subsequent logs will include request_id
    """
    request_id_ctx.set(request_id)


def clear_request_id():
    """Clear request ID from context."""
    request_id_ctx.set(None)


def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return StructuredLogger(name)


# Convenience functions for module-level logging

def log_debug(message: str, **context):
    """Log debug message."""
    logger = StructuredLogger(__name__)
    logger.debug(message, **context)


def log_info(message: str, **context):
    """Log info message."""
    logger = StructuredLogger(__name__)
    logger.info(message, **context)


def log_warning(message: str, **context):
    """Log warning message."""
    logger = StructuredLogger(__name__)
    logger.warning(message, **context)


def log_error(message: str, **context):
    """Log error message."""
    logger = StructuredLogger(__name__)
    logger.error(message, **context)


def log_critical(message: str, **context):
    """Log critical message."""
    logger = StructuredLogger(__name__)
    logger.critical(message, **context)


def log_exception(message: str, **context):
    """Log exception with traceback."""
    logger = StructuredLogger(__name__)
    logger.exception(message, **context)
