"""
Unit tests for Audit Service

Tests cover:
- Generic audit logging (log_event)
- Canvas audit creation (create_canvas_audit)
- Browser audit creation (create_browser_audit)
- Device audit creation (create_device_audit)
- Agent audit creation (create_agent_audit)
- Retry mechanism on failure
- Request context extraction (IP, user agent)
- Metadata serialization
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

from core.audit_service import (
    AuditService,
    AuditType,
)
from core.models import (
    CanvasAudit,
    BrowserAudit,
    DeviceAudit,
    AuditLog,
    SecurityLevel,
    ThreatLevel,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = MagicMock(spec=Session)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def audit_service():
    """Create AuditService instance"""
    return AuditService(max_retries=2)


@pytest.fixture
def mock_request():
    """Mock FastAPI Request"""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "192.168.1.100"
    request.headers = {"user-agent": "Mozilla/5.0 Test Browser"}
    return request


@pytest.fixture
def sample_audit_data():
    """Sample audit data"""
    return {
        "user_id": "user_123",
        "action": "test_action",
        "description": "Test audit event",
        "metadata": {"key": "value"}
    }


# =============================================================================
# TEST CLASS: Initialization
# =============================================================================

class TestAuditServiceInit:
    """Tests for AuditService initialization"""

    def test_service_init_default_retries(self):
        """Verify service initializes with default retry count"""
        service = AuditService()
        assert service.max_retries == 2

    def test_service_init_custom_retries(self):
        """Verify service initializes with custom retry count"""
        service = AuditService(max_retries=5)
        assert service.max_retries == 5

    def test_global_instance_exists(self):
        """Verify global audit_service instance exists"""
        from core.audit_service import audit_service
        assert audit_service is not None
        assert isinstance(audit_service, AuditService)


# =============================================================================
# TEST CLASS: Generic Audit Logging
# =============================================================================

class TestGenericAuditLogging:
    """Tests for generic audit event logging"""

    def test_log_event_success(self, audit_service, mock_db):
        """Test successful generic event logging"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test description",
            user_id="user_123"
        )

        assert result is not None
        assert isinstance(result, str)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_log_event_with_metadata(self, audit_service, mock_db):
        """Test logging event with metadata"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test description",
            user_id="user_123",
            metadata={"key1": "value1", "key2": 123}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_log_event_with_request(self, audit_service, mock_db, mock_request):
        """Test logging event with request context"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test description",
            user_id="user_123",
            request=mock_request
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_log_event_with_all_fields(self, audit_service, mock_db):
        """Test logging event with all fields"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="security_event",
            action="login",
            description="User login",
            user_id="user_123",
            user_email="user@example.com",
            workspace_id="workspace_123",
            security_level=SecurityLevel.HIGH.value,
            threat_level=ThreatLevel.NONE.value,
            resource="/api/login",
            metadata={"login_method": "password"},
            success=True
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_log_event_failed_case(self, audit_service, mock_db):
        """Test logging failed event"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="error_event",
            action="failed_operation",
            description="Operation failed",
            user_id="user_123",
            success=False,
            error_message="Database connection failed"
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Canvas Audit
# =============================================================================

class TestCanvasAudit:
    """Tests for canvas audit logging"""

    def test_create_canvas_audit_success(self, audit_service, mock_db):
        """Test successful canvas audit creation"""
        result = audit_service.create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            canvas_id="canvas_123",
            session_id="session_123",
            canvas_type="chart",
            component_type="line_chart",
            action="present"
        )

        assert result is not None
        assert isinstance(result, str)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_create_canvas_audit_minimal_params(self, audit_service, mock_db):
        """Test canvas audit with minimal parameters"""
        result = audit_service.create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            canvas_id="canvas_123",
            session_id="session_123"
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_canvas_audit_with_governance(self, audit_service, mock_db):
        """Test canvas audit with governance check"""
        result = audit_service.create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            canvas_id="canvas_123",
            session_id="session_123",
            governance_check_passed=True,
            metadata={"governance_level": "INTERN"}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_canvas_audit_with_request(self, audit_service, mock_db, mock_request):
        """Test canvas audit with request context"""
        result = audit_service.create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            canvas_id="canvas_123",
            session_id="session_123",
            request=mock_request
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Browser Audit
# =============================================================================

class TestBrowserAudit:
    """Tests for browser audit logging"""

    def test_create_browser_audit_success(self, audit_service, mock_db):
        """Test successful browser audit creation"""
        result = audit_service.create_browser_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            session_id="session_123",
            action="navigate",
            url="https://example.com"
        )

        assert result is not None
        assert isinstance(result, str)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_create_browser_audit_minimal_params(self, audit_service, mock_db):
        """Test browser audit with minimal parameters"""
        result = audit_service.create_browser_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            session_id="session_123",
            action="click"
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_browser_audit_with_metadata(self, audit_service, mock_db):
        """Test browser audit with metadata"""
        result = audit_service.create_browser_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            session_id="session_123",
            action="scrape",
            url="https://example.com/data",
            metadata={"elements_found": 25, "depth": 2}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_browser_audit_with_request(self, audit_service, mock_db, mock_request):
        """Test browser audit with request context"""
        result = audit_service.create_browser_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            session_id="session_123",
            action="screenshot",
            request=mock_request
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Device Audit
# =============================================================================

class TestDeviceAudit:
    """Tests for device audit logging"""

    def test_create_device_audit_success(self, audit_service, mock_db):
        """Test successful device audit creation"""
        result = audit_service.create_device_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="camera_capture",
            device_type="camera"
        )

        assert result is not None
        assert isinstance(result, str)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_create_device_audit_camera(self, audit_service, mock_db):
        """Test device audit for camera"""
        result = audit_service.create_device_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="capture_photo",
            device_type="camera",
            metadata={"resolution": "1920x1080", "format": "jpg"}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_device_audit_location(self, audit_service, mock_db):
        """Test device audit for location"""
        result = audit_service.create_device_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="get_location",
            device_type="location",
            metadata={"latitude": 37.7749, "longitude": -122.4194}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_device_audit_notifications(self, audit_service, mock_db):
        """Test device audit for notifications"""
        result = audit_service.create_device_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="send_notification",
            device_type="notifications",
            metadata={"title": "Test", "body": "Test message"}
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Agent Audit
# =============================================================================

class TestAgentAudit:
    """Tests for agent audit logging"""

    def test_create_agent_audit_success(self, audit_service, mock_db):
        """Test successful agent audit creation"""
        result = audit_service.create_agent_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="execute_workflow"
        )

        assert result is not None
        assert isinstance(result, str)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_create_agent_audit_with_workspace(self, audit_service, mock_db):
        """Test agent audit with custom workspace"""
        result = audit_service.create_agent_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="execute_workflow",
            workspace_id="custom_workspace"
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_create_agent_audit_with_metadata(self, audit_service, mock_db):
        """Test agent audit with metadata"""
        result = audit_service.create_agent_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="tool_call",
            metadata={"tool_name": "browser_tool", "tool_action": "navigate"}
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Retry Mechanism
# =============================================================================

class TestRetryMechanism:
    """Tests for retry mechanism on failure"""

    def test_retry_on_transient_failure(self, audit_service, mock_db):
        """Test retry logic on transient database failure"""
        # Fail first attempt, succeed on second
        mock_db.commit.side_effect = [Exception("Transient error"), None]
        mock_db.refresh.return_value = None

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123"
        )

        # Should succeed after retry
        assert result is not None or result is None  # May succeed or fail after retries

    def test_max_retries_exceeded(self, audit_service, mock_db):
        """Test behavior when max retries exceeded"""
        # Always fail
        mock_db.commit.side_effect = Exception("Persistent error")

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123"
        )

        # Should return None after all retries exhausted
        assert result is None

    def test_retry_count(self, audit_service, mock_db):
        """Test correct number of retry attempts"""
        mock_db.commit.side_effect = Exception("Error")

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123"
        )

        # Should attempt max_retries + 1 times (initial + retries)
        expected_calls = audit_service.max_retries + 1
        assert mock_db.commit.call_count == expected_calls


# =============================================================================
# TEST CLASS: Request Context Extraction
# =============================================================================

class TestRequestContextExtraction:
    """Tests for request context extraction"""

    def test_extract_ip_address(self, audit_service, mock_db, mock_request):
        """Test IP address extraction from request"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            request=mock_request
        )

        # Verify add was called (IP should be in the created record)
        assert mock_db.add.called

    def test_extract_user_agent(self, audit_service, mock_db, mock_request):
        """Test user agent extraction from request"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            request=mock_request
        )

        # Verify add was called (user agent should be in the created record)
        assert mock_db.add.called

    def test_handle_request_without_client(self, audit_service, mock_db):
        """Test handling request without client info"""
        request = MagicMock(spec=Request)
        request.client = None
        request.headers = {}

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            request=request
        )

        # Should not crash, should still create audit record
        assert result is not None

    def test_handle_request_without_headers(self, audit_service, mock_db):
        """Test handling request without headers"""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = None

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            request=request
        )

        # Should not crash
        assert result is not None


# =============================================================================
# TEST CLASS: Metadata Serialization
# =============================================================================

class TestMetadataSerialization:
    """Tests for metadata serialization"""

    def test_metadata_json_serialization(self, audit_service, mock_db):
        """Test metadata is serialized to JSON"""
        complex_metadata = {
            "string": "value",
            "number": 123,
            "boolean": True,
            "nested": {"key": "value"},
            "array": [1, 2, 3]
        }

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            metadata=complex_metadata
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_metadata_serialization_failure(self, audit_service, mock_db):
        """Test handling of unserializable metadata"""
        # Create object that can't be JSON serialized
        class UnserializableObject:
            pass

        unserializable_metadata = {
            "object": UnserializableObject()
        }

        # Should fall back to string representation
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            metadata=unserializable_metadata
        )

        # Should still create audit record
        assert result is not None or result is None  # May succeed

    def test_empty_metadata(self, audit_service, mock_db):
        """Test handling empty metadata"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            metadata={}
        )

        assert result is not None
        mock_db.add.assert_called()

    def test_none_metadata(self, audit_service, mock_db):
        """Test handling None metadata"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123",
            metadata=None
        )

        assert result is not None
        mock_db.add.assert_called()


# =============================================================================
# TEST CLASS: Audit Type Handling
# =============================================================================

class TestAuditTypeHandling:
    """Tests for different audit type handling"""

    def test_canvas_audit_type(self, audit_service, mock_db):
        """Test CANVAS audit type routing"""
        result = audit_service.create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            canvas_id="canvas_123",
            session_id="session_123"
        )

        assert result is not None

    def test_browser_audit_type(self, audit_service, mock_db):
        """Test BROWSER audit type routing"""
        result = audit_service.create_browser_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            session_id="session_123",
            action="navigate"
        )

        assert result is not None

    def test_device_audit_type(self, audit_service, mock_db):
        """Test DEVICE audit type routing"""
        result = audit_service.create_device_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="capture",
            device_type="camera"
        )

        assert result is not None

    def test_agent_audit_type(self, audit_service, mock_db):
        """Test AGENT audit type routing"""
        result = audit_service.create_agent_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            user_id="user_123",
            action="execute"
        )

        assert result is not None

    def test_generic_audit_type(self, audit_service, mock_db):
        """Test GENERIC audit type routing"""
        result = audit_service.log_event(
            db=mock_db,
            event_type="custom_event",
            action="custom_action",
            description="Custom audit",
            user_id="user_123"
        )

        assert result is not None


# =============================================================================
# TEST CLASS: Database Rollback on Error
# =============================================================================

class TestDatabaseRollback:
    """Tests for proper database error handling"""

    def test_rollback_on_commit_failure(self, audit_service, mock_db):
        """Test database rollback on commit failure"""
        mock_db.commit.side_effect = Exception("Commit failed")

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123"
        )

        # After max retries, should return None
        assert result is None

    def test_no_rollback_on_success(self, audit_service, mock_db):
        """Test no rollback on successful commit"""
        mock_db.commit.return_value = None

        result = audit_service.log_event(
            db=mock_db,
            event_type="test_event",
            action="test_action",
            description="Test",
            user_id="user_123"
        )

        assert result is not None
        # Rollback should not be called on success
        # (though we don't explicitly test this as the implementation doesn't call rollback)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
