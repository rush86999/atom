"""
Standardized Logging Utilities for ATOM Platform
Provides consistent logging format across all services
"""

import json
import logging
import sys
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class LogLevel(Enum):
    """Standardized log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext:
    """Context information for structured logging"""

    def __init__(
        self,
        service: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        integration: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ):
        self.service = service
        self.user_id = user_id
        self.request_id = request_id
        self.integration = integration
        self.workflow_id = workflow_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging"""
        context = {
            "service": self.service,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if self.user_id:
            context["user_id"] = self.user_id
        if self.request_id:
            context["request_id"] = self.request_id
        if self.integration:
            context["integration"] = self.integration
        if self.workflow_id:
            context["workflow_id"] = self.workflow_id

        return context


class StructuredLogger:
    """
    Structured logger that provides consistent logging format
    across all ATOM platform services
    """

    def __init__(self, name: str, context: Optional[LogContext] = None):
        self.logger = logging.getLogger(name)
        self.context = context or LogContext(service=name)

        # Ensure we have at least one handler
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _format_message(
        self,
        level: LogLevel,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> str:
        """Format log message as structured JSON"""
        log_entry = {"level": level.value, "message": message, **self.context.to_dict()}

        if extra_data:
            log_entry["extra_data"] = extra_data

        if exception:
            log_entry["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc(),
            }

        return json.dumps(log_entry, default=str)

    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        formatted_message = self._format_message(LogLevel.DEBUG, message, extra_data)
        self.logger.debug(formatted_message)

    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log info message"""
        formatted_message = self._format_message(LogLevel.INFO, message, extra_data)
        self.logger.info(formatted_message)

    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        formatted_message = self._format_message(LogLevel.WARNING, message, extra_data)
        self.logger.warning(formatted_message)

    def error(
        self,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """Log error message with optional exception"""
        formatted_message = self._format_message(
            LogLevel.ERROR, message, extra_data, exception
        )
        self.logger.error(formatted_message)

    def critical(
        self,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """Log critical message with optional exception"""
        formatted_message = self._format_message(
            LogLevel.CRITICAL, message, extra_data, exception
        )
        self.logger.critical(formatted_message)


# Factory function for creating loggers
def get_logger(
    service_name: str,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    integration: Optional[str] = None,
) -> StructuredLogger:
    """
    Factory function to create structured loggers

    Args:
        service_name: Name of the service creating the logger
        user_id: Optional user identifier
        request_id: Optional request identifier
        integration: Optional integration name

    Returns:
        StructuredLogger instance
    """
    context = LogContext(
        service=service_name,
        user_id=user_id,
        request_id=request_id,
        integration=integration,
    )
    return StructuredLogger(service_name, context)


# Integration-specific loggers
def get_integration_logger(
    integration_name: str, user_id: Optional[str] = None
) -> StructuredLogger:
    """Get logger for specific integration"""
    return get_logger(
        service_name=f"integration.{integration_name}",
        user_id=user_id,
        integration=integration_name,
    )


def get_workflow_logger(
    workflow_id: str, user_id: Optional[str] = None
) -> StructuredLogger:
    """Get logger for specific workflow"""
    context = LogContext(service="workflow", user_id=user_id, workflow_id=workflow_id)
    return StructuredLogger(f"workflow.{workflow_id}", context)


def get_api_logger(request_id: str, user_id: Optional[str] = None) -> StructuredLogger:
    """Get logger for API requests"""
    return get_logger(service_name="api", user_id=user_id, request_id=request_id)


# Error handling utilities
def log_integration_error(
    integration_name: str,
    error_message: str,
    exception: Optional[Exception] = None,
    user_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
):
    """Standardized error logging for integrations"""
    logger = get_integration_logger(integration_name, user_id)
    logger.error(error_message, extra_data, exception)


def log_workflow_error(
    workflow_id: str,
    error_message: str,
    exception: Optional[Exception] = None,
    user_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
):
    """Standardized error logging for workflows"""
    logger = get_workflow_logger(workflow_id, user_id)
    logger.error(error_message, extra_data, exception)


def log_api_error(
    request_id: str,
    error_message: str,
    exception: Optional[Exception] = None,
    user_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
):
    """Standardized error logging for API requests"""
    logger = get_api_logger(request_id, user_id)
    logger.error(error_message, extra_data, exception)


# Performance logging
def log_performance_metric(
    service_name: str,
    metric_name: str,
    value: float,
    unit: str = "ms",
    user_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
):
    """Log performance metrics"""
    logger = get_logger(service_name, user_id)
    performance_data = {
        "metric": metric_name,
        "value": value,
        "unit": unit,
        **(extra_data or {}),
    }
    logger.info(f"Performance metric: {metric_name}", performance_data)


# Security logging
def log_security_event(
    event_type: str,
    description: str,
    user_id: Optional[str] = None,
    severity: str = "INFO",
    extra_data: Optional[Dict[str, Any]] = None,
):
    """Log security-related events"""
    logger = get_logger("security", user_id)
    security_data = {
        "event_type": event_type,
        "severity": severity,
        "description": description,
        **(extra_data or {}),
    }

    if severity.upper() == "CRITICAL":
        logger.critical(f"Security event: {event_type}", security_data)
    elif severity.upper() == "ERROR":
        logger.error(f"Security event: {event_type}", security_data)
    elif severity.upper() == "WARNING":
        logger.warning(f"Security event: {event_type}", security_data)
    else:
        logger.info(f"Security event: {event_type}", security_data)


# Configuration function
def configure_logging(level: str = "INFO", format: str = "json"):
    """
    Configure global logging settings

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format (json, text)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Clear existing handlers
    logging.getLogger().handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if format == "json":
        # JSON format is handled by StructuredLogger
        formatter = logging.Formatter("%(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(level=log_level, handlers=[handler], force=True)


# Initialize with default configuration
configure_logging(level="INFO", format="json")
