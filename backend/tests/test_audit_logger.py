"""
Tests for Audit Logger

Tests audit logging functionality:
- Log integration call captures metadata
- Log integration error captures error
- Audit log format is structured
- Audit log includes timestamp
- Sensitive parameters are sanitized
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

    def test_audit_log_creates_with_required_fields(self):
        """Test that audit log is created with required fields"""
        log = IntegrationAuditLog(
            connector_id="gmail",
            method="send_email",
            params={"to": "test@example.com"}
        )

        assert log.connector_id == "gmail"
        assert log.method == "send_email"
        assert log.params == {"to": "test@example.com"}
        assert log.result is None
        assert log.error is None
        assert log.timestamp > 0

    def test_audit_log_to_dict_is_structured(self):
        """Test that audit log to_dict returns structured format"""
        log = IntegrationAuditLog(
            connector_id="slack",
            method="send_message",
            params={"channel": "#general", "text": "Hello"},
            result={"success": True}
        )

        log_dict = log.to_dict()

        assert isinstance(log_dict, dict)
        assert "connector_id" in log_dict
        assert "method" in log_dict
        assert "params" in log_dict
        assert "result" in log_dict
        assert "timestamp" in log_dict
        assert "epoch" in log_dict

    def test_audit_log_includes_timestamp(self):
        """Test that audit log includes timestamp"""
        before_time = time.time()
        log = IntegrationAuditLog(
            connector_id="jira",
            method="create_issue",
            params={}
        )
        after_time = time.time()

        assert log.timestamp >= before_time
        assert log.timestamp <= after_time

        # Check ISO format in to_dict
        log_dict = log.to_dict()
        assert "T" in log_dict["timestamp"]  # ISO format
        assert "Z" in log_dict["timestamp"] or "+" in log_dict["timestamp"]

    def test_audit_log_sanitizes_sensitive_params(self):
        """Test that sensitive parameters are redacted"""
        log = IntegrationAuditLog(
            connector_id="gmail",
            method="send_email",
            params={
                "to": "test@example.com",
                "password": "secret123",
                "api_key": "key_abc",
                "subject": "Test"
            }
        )

        log_dict = log.to_dict()

        # Sensitive fields should be redacted
        assert log_dict["params"]["password"] == "***REDACTED***"
        assert log_dict["params"]["api_key"] == "***REDACTED***"

        # Non-sensitive fields should remain
        assert log_dict["params"]["to"] == "test@example.com"
        assert log_dict["params"]["subject"] == "Test"

    def test_audit_log_sanitizes_nested_sensitive_params(self):
        """Test that nested sensitive parameters are redacted"""
        log = IntegrationAuditLog(
            connector_id="slack",
            method="send_message",
            params={
                "message": "Hello",
                "credentials": {
                    "token": "xoxb-secret",
                    "refresh_token": "refresh-secret"
                }
            }
        )

        log_dict = log.to_dict()

        # Nested sensitive fields should be redacted
        assert log_dict["params"]["credentials"]["token"] == "***REDACTED***"
        assert log_dict["params"]["credentials"]["refresh_token"] == "***REDACTED***"
        assert log_dict["params"]["message"] == "Hello"


class TestLogIntegrationCall:
    """Test log_integration_call function"""

    def test_log_integration_call_creates_audit_log(self):
        """Test that log_integration_call creates an audit log entry"""
        log = log_integration_call(
            connector_id="gmail",
            method="send_email",
            params={"to": "test@example.com"},
            result={"success": True, "message_id": "123"}
        )

        assert isinstance(log, IntegrationAuditLog)
        assert log.connector_id == "gmail"
        assert log.method == "send_email"
        assert log.result == {"success": True, "message_id": "123"}
        assert log.error is None

    def test_log_integration_call_captures_metadata(self):
        """Test that log_integration_call captures all metadata"""
        log = log_integration_call(
            connector_id="jira",
            method="get_issue",
            params={"issue_key": "PROJ-123"},
            result={"summary": "Test issue"}
        )

        log_dict = log.to_dict()

        assert log_dict["connector_id"] == "jira"
        assert log_dict["method"] == "get_issue"
        assert log_dict["params"]["issue_key"] == "PROJ-123"
        assert log_dict["result"]["summary"] == "Test issue"
        assert "timestamp" in log_dict


class TestLogIntegrationError:
    """Test log_integration_error function"""

    def test_log_integration_error_creates_audit_log(self):
        """Test that log_integration_error creates an audit log entry"""
        error = Exception("API rate limit exceeded")

        log = log_integration_error(
            connector_id="slack",
            method="send_message",
            error=error,
            params={"channel": "#general"}
        )

        assert isinstance(log, IntegrationAuditLog)
        assert log.connector_id == "slack"
        assert log.method == "send_message"
        assert log.error == "API rate limit exceeded"
        assert log.result is None

    def test_log_integration_error_captures_error(self):
        """Test that log_integration_error captures error details"""
        error = ValueError("Invalid credentials")

        log = log_integration_error(
            connector_id="jira",
            method="create_issue",
            error=error
        )

        assert log.error == "Invalid credentials"
        assert log.params == {}  # Default empty params


class TestLogIntegrationTiming:
    """Test log_integration_attempt and log_integration_complete"""

    def test_log_integration_attempt_creates_context(self):
        """Test that log_integration_attempt creates timing context"""
        context = log_integration_attempt(
            connector_id="gmail",
            method="send_email",
            params={"to": "test@example.com"}
        )

        assert isinstance(context, dict)
        assert "connector_id" in context
        assert "method" in context
        assert "start_time" in context
        assert "params" in context

    def test_log_integration_complete_calculates_duration(self):
        """Test that log_integration_complete calculates duration"""
        context = log_integration_attempt(
            connector_id="slack",
            method="send_message",
            params={"channel": "#general"}
        )

        # Simulate some work
        import time
        time.sleep(0.01)

        duration_ms = log_integration_complete(
            context=context,
            result={"success": True}
        )

        assert duration_ms >= 10  # At least 10ms
        assert duration_ms < 100  # Less than 100ms

    def test_log_integration_complete_handles_error(self):
        """Test that log_integration_complete handles errors"""
        context = log_integration_attempt(
            connector_id="jira",
            method="get_issue",
            params={"issue_key": "PROJ-123"}
        )

        error = Exception("Issue not found")
        duration_ms = log_integration_complete(
            context=context,
            error=error
        )

        assert duration_ms >= 0
        # Error should be logged internally


class TestAuditLogFormatting:
    """Test audit log formatting and structure"""

    def test_audit_log_format_is_structured(self):
        """Test that audit log has consistent structured format"""
        log = IntegrationAuditLog(
            connector_id="gmail",
            method="send_email",
            params={"to": "test@example.com"},
            result={"success": True}
        )

        log_dict = log.to_dict()

        # Check all required fields exist
        required_fields = ["connector_id", "method", "params", "result", "error", "timestamp", "epoch"]
        for field in required_fields:
            assert field in log_dict, f"Missing field: {field}"

        # Check data types
        assert isinstance(log_dict["connector_id"], str)
        assert isinstance(log_dict["method"], str)
        assert isinstance(log_dict["params"], dict)
        assert isinstance(log_dict["timestamp"], str)
        assert isinstance(log_dict["epoch"], float)

    def test_multiple_audit_logs_have_unique_timestamps(self):
        """Test that multiple audit logs have unique timestamps"""
        import time

        log1 = IntegrationAuditLog(
            connector_id="gmail",
            method="send_email",
            params={}
        )

        time.sleep(0.01)  # Small delay

        log2 = IntegrationAuditLog(
            connector_id="slack",
            method="send_message",
            params={}
        )

        assert log1.timestamp != log2.timestamp
        assert log2.timestamp > log1.timestamp
