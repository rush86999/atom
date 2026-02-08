"""
Standardized Logging Configuration for Atom Platform

Provides consistent logging format across all modules with:
- Colored console output
- File logging
- Correlation ID tracking
- Structured context variables
- Request tracing

Feature Flags:
    LOG_LEVEL: Logging level (default: INFO)
    LOG_FILE: Path to log file (default: None)
    LOG_FORMAT: json or text (default: text)
"""

from contextvars import ContextVar
from datetime import datetime
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import uuid

# ============================================================================
# Context Variables for Request Tracking
# ============================================================================

# Context Variables for Request Tracking
# Note: ContextVar doesn't support default values, so we use .get() with fallback

CORRELATION_ID: ContextVar[str] = ContextVar('correlation_id')
USER_ID: ContextVar[str] = ContextVar('user_id')
REQUEST_ID: ContextVar[str] = ContextVar('request_id')


def bind_context(**kwargs):
    """
    Bind context variables for the current request/task.

    This should be called at the start of each request to initialize
    tracking context that will be available in all log messages.

    Args:
        **kwargs: Context variables to bind (correlation_id, user_id, request_id, etc.)

    Example:
        # In FastAPI middleware
        @app.middleware("http")
        async def add_context(request: Request, call_next):
            correlation_id = str(uuid.uuid4())
            bind_context(
                correlation_id=correlation_id,
                user_id=getattr(request.state, "user_id", None),
                request_id=correlation_id
            )
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        # In your application code
        logger.info("Processing request")  # Automatically includes correlation_id
    """
    for key, value in kwargs.items():
        if value is not None:
            if key == "correlation_id":
                CORRELATION_ID.set(str(value))
            elif key == "user_id":
                USER_ID.set(str(value))
            elif key == "request_id":
                REQUEST_ID.set(str(value))


def get_context() -> Dict[str, str]:
    """Get all current context variables"""
    try:
        return {
            "correlation_id": CORRELATION_ID.get(),
            "user_id": USER_ID.get(),
            "request_id": REQUEST_ID.get(),
        }
    except LookupError:
        # Context variables not set yet
        return {
            "correlation_id": "",
            "user_id": "",
            "request_id": "",
        }


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


# ANSI color codes for terminal output
class LogColors:
    """ANSI color codes for log levels"""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    GREY = "\033[90m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RED_BOLD = "\033[1;91m"
    CYAN = "\033[96m"


class ColoredFormatter(logging.Formatter):
    """
    Custom log formatter with colors for console output.

    Format: [TIMESTAMP] [LEVEL] [CORRELATION_ID] [LOGGER_NAME] MESSAGE

    Automatically includes correlation ID, user ID, and request ID
    from context variables when available.
    """

    COLORS = {
        logging.DEBUG: LogColors.GREY,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED_BOLD,
    }

    def __init__(self, use_colors: bool = True, show_logger_name: bool = True, show_context: bool = True):
        """
        Args:
            use_colors: Enable ANSI color codes (default: True)
            show_logger_name: Include logger name in output (default: True)
            show_context: Include correlation ID and other context (default: True)
        """
        super().__init__()
        self.use_colors = use_colors
        self.show_logger_name = show_logger_name
        self.show_context = show_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and structured information"""

        # Color the level name
        levelname = record.levelname
        if self.use_colors and record.levelno in self.COLORS:
            levelname = f"{self.COLORS[record.levelno]}{levelname}{LogColors.RESET}"

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Build the log message
        parts = [
            f"[{timestamp}]",
            f"[{levelname}]"
        ]

        # Add context variables (correlation_id, user_id, request_id)
        if self.show_context:
            correlation_id = CORRELATION_ID.get()
            if correlation_id:
                # Show last 8 characters for readability
                short_id = correlation_id[-8:] if len(correlation_id) > 8 else correlation_id
                parts.append(f"[{LogColors.CYAN}{short_id}{LogColors.RESET}]")

            user_id = USER_ID.get()
            if user_id:
                parts.append(f"[user:{user_id[:8]}]")

        if self.show_logger_name:
            parts.append(f"[{record.name}]")

        # Add the message
        message = record.getMessage()

        # Add exception info if present
        if record.exc_info:
            if not message.endswith('\n'):
                message += '\n'
            message += self.formatException(record.exc_info)

        parts.append(message)

        return " ".join(parts)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_colors: bool = True,
    show_logger_name: bool = True
) -> None:
    """
    Setup application-wide logging configuration.

    This should be called once at application startup in main.py:
    ```python
    from core.logging_config import setup_logging
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "logs/atom.log")
    )
    ```

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to LOG_LEVEL environment variable or INFO
        log_file: Path to log file. If provided, logs will be written to file
                  in addition to console. Defaults to LOG_FILE environment variable
        enable_colors: Enable ANSI colors in console output (default: True)
        show_logger_name: Include logger name in output (default: True)

    Environment Variables:
        LOG_LEVEL: Logging level (default: INFO)
        LOG_FILE: Path to log file (default: None)
        LOG_FORMAT: json or text (default: text)

    Examples:
        # Basic setup
        setup_logging()

        # With custom level and file
        setup_logging(level="DEBUG", log_file="logs/debug.log")

        # Without colors (for production logs)
        setup_logging(enable_colors=False)
    """
    # Determine log level
    log_level_str = level or os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(
        use_colors=enable_colors,
        show_logger_name=show_logger_name
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log file specified)
    if log_file or os.getenv("LOG_FILE"):
        file_path = Path(log_file or os.getenv("LOG_FILE"))
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(log_level)

        # Use plain text format for files (no colors)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy library logs
    _configure_library_loggers()

    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {log_level_str} level")
    if log_file:
        logger.info(f"Logging to file: {file_path}")


def _configure_library_loggers() -> None:
    """
    Configure log levels for third-party libraries to reduce noise.

    Most libraries are too chatty at INFO level, so we set them to WARNING.
    """
    # Uvicorn/FastAPI
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # SQLAlchemy
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Other common libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    This is the preferred way to get loggers in modules:
    ```python
    from core.logging_config import get_logger
    logger = get_logger(__name__)
    ```

    Args:
        name: Logger name (typically use __name__)

    Returns:
        Logger instance

    Examples:
        # In your modules
        from core.logging_config import get_logger
        logger = get_logger(__name__)

        # Use the logger
        logger.info("Processing started")
        logger.error("Processing failed", exc_info=True)
    """
    return logging.getLogger(name)


class LoggerContext:
    """
    Context manager for temporary logging level changes.

    Useful for debugging specific sections of code:

    ```python
    with LoggerContext("sqlalchemy.engine", logging.DEBUG):
        # This section will log SQL queries
        result = db.query(Model).all()
    # Logging level restored automatically
    ```

    Args:
        logger_name: Name of the logger to modify
        level: Temporary log level
    """

    def __init__(self, logger_name: str, level: int):
        self.logger_name = logger_name
        self.new_level = level
        self.old_level = None

    def __enter__(self):
        logger = logging.getLogger(self.logger_name)
        self.old_level = logger.level
        logger.setLevel(self.new_level)
        return logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.old_level)


# ============================================================================
# FastAPI Integration
# ============================================================================

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to automatically add logging context to all requests.

    Adds correlation IDs, user IDs, and request IDs to context variables
    that are automatically included in all log messages.

    Usage:
        app = FastAPI()
        app.add_middleware(LoggingContextMiddleware)

    This middleware:
    1. Generates a correlation ID for each request
    2. Extracts user ID from request state (if set by auth middleware)
    3. Adds X-Correlation-ID header to responses
    4. Makes context available to all loggers during request handling
    """

    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Extract user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        # Bind context for this request
        bind_context(
            correlation_id=correlation_id,
            user_id=user_id,
            request_id=correlation_id
        )

        # Store correlation ID in request state for access in endpoints
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


def get_correlation_id() -> str:
    """
    Get the current correlation ID from context.

    Can be called from anywhere in the application during request handling.

    Returns:
        Correlation ID string (empty if not set)
    """
    return CORRELATION_ID.get()


# ============================================================================
# Structured Logging Helper
# ============================================================================

class StructuredLogger:
    """
    Helper for structured logging with automatic context inclusion.

    Example:
        from core.logging_config import StructuredLogger

        logger = StructuredLogger(__name__)
        logger.info("User logged in", extra={"user_email": "user@example.com", "ip": "1.2.3.4"})
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add context variables to extra dict"""
        context = {}
        context.update(get_context())
        if extra:
            context.update(extra)
        return context

    def debug(self, msg: str, **kwargs):
        """Log debug message with context"""
        self._logger.debug(msg, extra=self._add_context(kwargs.get("extra")))

    def info(self, msg: str, **kwargs):
        """Log info message with context"""
        self._logger.info(msg, extra=self._add_context(kwargs.get("extra")))

    def warning(self, msg: str, **kwargs):
        """Log warning message with context"""
        self._logger.warning(msg, extra=self._add_context(kwargs.get("extra")))

    def error(self, msg: str, **kwargs):
        """Log error message with context"""
        self._logger.error(msg, extra=self._add_context(kwargs.get("extra")), exc_info=kwargs.get("exc_info", True))

    def critical(self, msg: str, **kwargs):
        """Log critical message with context"""
        self._logger.critical(msg, extra=self._add_context(kwargs.get("extra")), exc_info=kwargs.get("exc_info", True))
