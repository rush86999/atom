"""
Tests for Integration Audit Logger governance pattern

Tests the single-tenant audit logger implementation for integrations.
"""
import pytest
import time
from core.audit_logger import (
    IntegrationAuditLog,
    log_integration_call,
    log_integration_error,
    log_integration_attempt,
    log_integration_complete
)


class TestIntegrationAuditLog:
    """Test IntegrationAuditLog model"""

    def test_audit_log_initialization(self):
        """Test audit log initializes correctly"""
        log = IntegrationAuditLog(
            connector_id="test_integration",
            method="test_method",
            params={"key": "value"}
        )
        assert log.connector_id == "test_integration"
        assert log.method == "test_method"
        assert log.params == {"key": "value"}
        assert log.result is None
        assert log.error is None
        assert log.timestamp > 0

    def test_audit_log_to_dict(self):
        """Test converting audit log to dictionary"""
        log = IntegrationAuditLog(
            connector_id="gmail",
            method="send_message",
            params={"to": "test@example.com"},
            result={"message_id": "12345"}
        )
        log_dict = log.to_dict()
        assert log_dict["connector_id"] == "gmail"
        assert log_dict["method"] == "send_message"
        assert log_dict["params"]["to"] == "test@example.com"
        assert log_dict["result"]["message_id"] == "12345"
        assert "timestamp" in log_dict
        assert "epoch" in log_dict

    def test_audit_log_sanitizes_passwords(self):
        """Test audit log sanitizes password fields"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={"username": "user", "password": "secret123"}
        )
        log_dict = log.to_dict()
        assert log_dict["params"]["username"] == "user"
        assert log_dict["params"]["password"] == "***REDACTED***"

    def test_audit_log_sanitizes_tokens(self):
        """Test audit log sanitizes token fields"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={"access_token": "xyz123", "data": "safe"}
        )
        log_dict = log.to_dict()
        assert log_dict["params"]["access_token"] == "***REDACTED***"
        assert log_dict["params"]["data"] == "safe"

    def test_audit_log_sanitizes_api_keys(self):
        """Test audit log sanitizes API key fields"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={"api_key": "key123", "other": "value"}
        )
        log_dict = log.to_dict()
        assert log_dict["params"]["api_key"] == "***REDACTED***"
        assert log_dict["params"]["other"] == "value"

    def test_audit_log_sanitizes_secrets(self):
        """Test audit log sanitizes secret fields"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={"client_secret": "secret123"}
        )
        log_dict = log.to_dict()
        assert log_dict["params"]["client_secret"] == "***REDACTED***"

    def test_audit_log_sanitizes_nested_dicts(self):
        """Test audit log sanitizes nested dictionaries"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={
                "credentials": {
                    "password": "secret123",
                    "username": "user"
                }
            }
        )
        log_dict = log.to_dict()
        assert log_dict["params"]["credentials"]["password"] == "***REDACTED***"
        assert log_dict["params"]["credentials"]["username"] == "user"


class TestLogIntegrationCall:
    """Test log_integration_call function"""

    def test_log_integration_call_returns_audit_log(self):
        """Test log_integration_call returns IntegrationAuditLog"""
        log = log_integration_call(
            connector_id="gmail",
            method="send_message",
            params={"to": "test@example.com"},
            result={"message_id": "12345"}
        )
        assert isinstance(log, IntegrationAuditLog)
        assert log.connector_id == "gmail"
        assert log.method == "send_message"
        assert log.result is not None
        assert log.error is None

    def test_log_integration_call_without_result(self):
        """Test log_integration_call works without result"""
        log = log_integration_call(
            connector_id="slack",
            method="post_message",
            params={"channel": "#test", "text": "Hello"}
        )
        assert log.connector_id == "slack"
        assert log.method == "post_message"
        assert log.error is None


class TestLogIntegrationError:
    """Test log_integration_error function"""

    def test_log_integration_error_returns_audit_log(self):
        """Test log_integration_error returns IntegrationAuditLog"""
        error = Exception("Test error")
        log = log_integration_error(
            connector_id="jira",
            method="create_issue",
            error=error,
            params={"project": "TEST"}
        )
        assert isinstance(log, IntegrationAuditLog)
        assert log.connector_id == "jira"
        assert log.method == "create_issue"
        assert log.error == "Test error"
        assert log.result is None

    def test_log_integration_error_without_params(self):
        """Test log_integration_error works without params"""
        error = ValueError("Invalid input")
        log = log_integration_error(
            connector_id="zoom",
            method="create_meeting",
            error=error
        )
        assert log.connector_id == "zoom"
        assert log.error == "Invalid input"
        assert log.params == {}


class TestLogIntegrationAttempt:
    """Test log_integration_attempt function"""

    def test_log_integration_attempt_returns_context(self):
        """Test log_integration_attempt returns context dict"""
        context = log_integration_attempt(
            connector_id="gmail",
            method="get_messages",
            params={"max_results": 50}
        )
        assert isinstance(context, dict)
        assert context["connector_id"] == "gmail"
        assert context["method"] == "get_messages"
        assert context["params"]["max_results"] == 50
        assert "start_time" in context
        assert context["start_time"] > 0

    def test_log_integration_attempt_captures_time(self):
        """Test log_integration_attempt captures start time"""
        before = time.time()
        context = log_integration_attempt("test", "test_method", {})
        after = time.time()
        assert before <= context["start_time"] <= after


class TestLogIntegrationComplete:
    """Test log_integration_complete function"""

    def test_log_integration_complete_with_success(self):
        """Test log_integration_complete with successful result"""
        context = log_integration_attempt("gmail", "send_message", {})
        time.sleep(0.01)  # Small delay to ensure measurable duration

        duration = log_integration_complete(
            context=context,
            result={"message_id": "12345"}
        )

        assert duration > 0
        assert duration >= 10  # At least 10ms

    def test_log_integration_complete_with_error(self):
        """Test log_integration_complete with error"""
        context = log_integration_attempt("jira", "create_issue", {})
        error = Exception("Creation failed")

        duration = log_integration_complete(
            context=context,
            error=error
        )

        assert duration > 0

    def test_log_integration_complete_returns_duration_ms(self):
        """Test log_integration_complete returns duration in milliseconds"""
        context = log_integration_attempt("test", "test_method", {})
        time.sleep(0.05)  # Sleep 50ms

        duration = log_integration_complete(context=context)

        # Should be approximately 50ms (with some tolerance)
        assert 40 <= duration <= 100

    def test_log_integration_complete_without_result_or_error(self):
        """Test log_integration_complete works without result or error"""
        context = log_integration_attempt("slack", "post_message", {})

        duration = log_integration_complete(context=context)

        assert duration >= 0


class TestAuditLogTimestamps:
    """Test audit log timestamp handling"""

    def test_custom_timestamp(self):
        """Test audit log with custom timestamp"""
        custom_time = 1234567890.0
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={},
            timestamp=custom_time
        )
        assert log.timestamp == custom_time

    def test_default_timestamp_is_current(self):
        """Test default timestamp is current time"""
        before = time.time()
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={}
        )
        after = time.time()
        assert before <= log.timestamp <= after


class TestAuditLogStructuredFormat:
    """Test audit log structured format"""

    def test_audit_log_has_iso_timestamp(self):
        """Test audit log includes ISO format timestamp"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={}
        )
        log_dict = log.to_dict()
        assert "timestamp" in log_dict
        # ISO format should include 'T' separator
        assert "T" in log_dict["timestamp"]

    def test_audit_log_includes_epoch(self):
        """Test audit log includes epoch timestamp"""
        log = IntegrationAuditLog(
            connector_id="test",
            method="test_method",
            params={}
        )
        log_dict = log.to_dict()
        assert "epoch" in log_dict
        assert isinstance(log_dict["epoch"], (int, float))

    def test_audit_log_includes_all_fields(self):
        """Test audit log includes all required fields"""
        log = IntegrationAuditLog(
            connector_id="gmail",
            method="send_message",
            params={"to": "test@example.com"},
            result={"message_id": "12345"}
        )
        log_dict = log.to_dict()
        required_fields = ["connector_id", "method", "params", "result", "error", "timestamp", "epoch"]
        for field in required_fields:
            assert field in log_dict


class TestAuditLogErrorHandling:
    """Test audit log error handling"""

    def test_log_with_exception_object(self):
        """Test logging with Exception object"""
        error = ValueError("Invalid value")
        log = log_integration_error(
            connector_id="test",
            method="test_method",
            error=error
        )
        assert "Invalid value" in log.error

    def test_log_with_custom_exception(self):
        """Test logging with custom exception"""
        class CustomError(Exception):
            pass

        error = CustomError("Custom error message")
        log = log_integration_error(
            connector_id="test",
            method="test_method",
            error=error
        )
        assert "Custom error message" in log.error

    def test_log_with_none_error(self):
        """Test logging with None error (success case)"""
        log = log_integration_call(
            connector_id="test",
            method="test_method",
            params={}
        )
        assert log.error is None
