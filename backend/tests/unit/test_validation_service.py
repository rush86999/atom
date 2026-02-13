"""
Unit tests for ValidationService

Tests cover:
- Initialization and configuration
- Agent configuration validation
- Canvas data validation
- Browser action validation
- Device action validation
- Execution request validation
- Bulk operation validation
- Pydantic model validation
- Error handling and edge cases
"""

import pytest
from pydantic import ValidationError, BaseModel

from core.validation_service import (
    ValidationService,
    ValidationResult,
    AgentConfigModel,
    CanvasDataModel,
    ExecutionRequestModel
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def validation_service():
    """Create a ValidationService instance"""
    return ValidationService()


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration"""
    return {
        "name": "Test Agent",
        "domain": "customer_support",
        "maturity_level": "INTERN",
        "temperature": 0.7,
        "max_tokens": 2000
    }


@pytest.fixture
def sample_canvas_data():
    """Sample canvas data"""
    return {
        "canvas_type": "generic",
        "component_type": "chart",
        "chart_type": "line",
        "title": "Sales Chart"
    }


@pytest.fixture
def valid_browser_params():
    """Valid browser action parameters"""
    return {
        "url": "https://example.com",
        "selector": "#submit-button"
    }


@pytest.fixture
def valid_device_params():
    """Valid device action parameters"""
    return {
        "device_node_id": "device-123",
        "message": "Test notification"
    }


# =============================================================================
# TEST CLASS: ValidationService Initialization
# =============================================================================

class TestValidationServiceInit:
    """Tests for ValidationService initialization"""

    def test_validation_service_init(self, validation_service):
        """Verify ValidationService initializes correctly"""
        assert validation_service is not None
        assert isinstance(validation_service, ValidationService)

    def test_validation_service_singleton_pattern(self):
        """Verify multiple instances can be created"""
        service1 = ValidationService()
        service2 = ValidationService()
        assert service1 is not service2  # Not a singleton


# =============================================================================
# TEST CLASS: ValidationResult
# =============================================================================

class TestValidationResult:
    """Tests for ValidationResult class"""

    def test_success_result(self):
        """Verify success result creation"""
        result = ValidationResult.success()
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.details == {}

    def test_error_result_single_message(self):
        """Verify error result with single message"""
        result = ValidationResult.error("Invalid input")
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Invalid input"

    def test_error_result_with_details(self):
        """Verify error result with details"""
        details = {"field": "name", "value": ""}
        result = ValidationResult.error("Name is required", details)
        assert result.is_valid is False
        assert result.details == details

    def test_multiple_errors(self):
        """Verify multiple errors result"""
        errors = ["Error 1", "Error 2", "Error 3"]
        result = ValidationResult.multiple(errors)
        assert result.is_valid is False
        assert len(result.errors) == 3
        assert result.errors == errors

    def test_multiple_errors_with_details(self):
        """Verify multiple errors with details"""
        errors = ["Field A invalid", "Field B invalid"]
        details = {"field_count": 2}
        result = ValidationResult.multiple(errors, details)
        assert result.is_valid is False
        assert result.details == details


# =============================================================================
# TEST CLASS: Agent Configuration Validation
# =============================================================================

class TestAgentConfigValidation:
    """Tests for agent configuration validation"""

    def test_validate_agent_config_valid(self, validation_service, sample_agent_config):
        """Verify valid agent configuration passes"""
        result = validation_service.validate_agent_config(sample_agent_config)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_agent_config_missing_name(self, validation_service):
        """Verify missing name is rejected"""
        config = {"domain": "customer_support"}
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("name" in error.lower() for error in result.errors)

    def test_validate_agent_config_empty_name(self, validation_service):
        """Verify empty name is rejected"""
        config = {"name": "   ", "domain": "customer_support"}
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("empty" in error.lower() or "name" in error.lower() for error in result.errors)

    def test_validate_agent_config_missing_domain(self, validation_service):
        """Verify missing domain is rejected"""
        config = {"name": "Test Agent"}
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("domain" in error.lower() for error in result.errors)

    def test_validate_agent_config_invalid_domain(self, validation_service):
        """Verify invalid domain is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "invalid_domain"
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("domain" in error.lower() for error in result.errors)

    def test_validate_agent_config_valid_domains(self, validation_service):
        """Verify all valid domains are accepted"""
        valid_domains = [
            "customer_support",
            "data_analysis",
            "content_creation",
            "automation",
            "research"
        ]
        for domain in valid_domains:
            config = {"name": "Test", "domain": domain}
            result = validation_service.validate_agent_config(config)
            assert result.is_valid, f"Domain {domain} should be valid"

    def test_validate_agent_config_invalid_maturity(self, validation_service):
        """Verify invalid maturity level is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INVALID"
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("maturity" in error.lower() for error in result.errors)

    def test_validate_agent_config_valid_maturity(self, validation_service):
        """Verify all valid maturity levels are accepted"""
        valid_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        for level in valid_levels:
            config = {
                "name": "Test",
                "domain": "customer_support",
                "maturity_level": level
            }
            result = validation_service.validate_agent_config(config)
            assert result.is_valid, f"Maturity level {level} should be valid"

    def test_validate_agent_config_invalid_temperature_low(self, validation_service):
        """Verify temperature below 0 is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "temperature": -0.5
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("temperature" in error.lower() for error in result.errors)

    def test_validate_agent_config_invalid_temperature_high(self, validation_service):
        """Verify temperature above 2 is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "temperature": 2.5
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("temperature" in error.lower() for error in result.errors)

    def test_validate_agent_config_valid_temperature(self, validation_service):
        """Verify valid temperature range is accepted"""
        valid_temps = [0, 0.5, 1.0, 1.5, 2.0]
        for temp in valid_temps:
            config = {
                "name": "Test",
                "domain": "customer_support",
                "temperature": temp
            }
            result = validation_service.validate_agent_config(config)
            assert result.is_valid, f"Temperature {temp} should be valid"

    def test_validate_agent_config_invalid_max_tokens_low(self, validation_service):
        """Verify max_tokens below 1 is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "max_tokens": 0
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("max_tokens" in error.lower() or "tokens" in error.lower() for error in result.errors)

    def test_validate_agent_config_invalid_max_tokens_high(self, validation_service):
        """Verify max_tokens above 32000 is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "max_tokens": 40000
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("max_tokens" in error.lower() or "tokens" in error.lower() for error in result.errors)

    def test_validate_agent_config_invalid_type_temperature(self, validation_service):
        """Verify non-numeric temperature is rejected"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "temperature": "high"
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert any("temperature" in error.lower() for error in result.errors)


# =============================================================================
# TEST CLASS: Canvas Data Validation
# =============================================================================

class TestCanvasDataValidation:
    """Tests for canvas data validation"""

    def test_validate_canvas_data_valid(self, validation_service, sample_canvas_data):
        """Verify valid canvas data passes"""
        result = validation_service.validate_canvas_data(sample_canvas_data)
        assert result.is_valid is True

    def test_validate_canvas_data_missing_canvas_type(self, validation_service):
        """Verify missing canvas_type is rejected"""
        data = {"component_type": "chart"}
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("canvas_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_missing_component_type(self, validation_service):
        """Verify missing component_type is rejected"""
        data = {"canvas_type": "generic"}
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("component_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_invalid_canvas_type(self, validation_service):
        """Verify invalid canvas_type is rejected"""
        data = {
            "canvas_type": "invalid_type",
            "component_type": "chart"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("canvas_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_valid_canvas_types(self, validation_service):
        """Verify all valid canvas types are accepted"""
        valid_types = [
            "generic", "docs", "email", "sheets", "orchestration",
            "terminal", "coding", "status_panel", "form"
        ]
        for canvas_type in valid_types:
            data = {
                "canvas_type": canvas_type,
                "component_type": "markdown"
            }
            result = validation_service.validate_canvas_data(data)
            assert result.is_valid, f"Canvas type {canvas_type} should be valid"

    def test_validate_canvas_data_invalid_generic_component(self, validation_service):
        """Verify invalid component_type for generic canvas is rejected"""
        data = {
            "canvas_type": "generic",
            "component_type": "invalid_component"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("component_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_valid_generic_components(self, validation_service):
        """Verify all valid generic component types are accepted"""
        valid_components = ["markdown", "form", "table", "image", "text"]
        for component in valid_components:
            data = {
                "canvas_type": "generic",
                "component_type": component
            }
            result = validation_service.validate_canvas_data(data)
            assert result.is_valid, f"Component {component} should be valid"

        # Chart component requires chart_type
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "line"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid, "Component chart should be valid with chart_type"

    def test_validate_canvas_data_chart_missing_type(self, validation_service):
        """Verify missing chart_type for chart component is rejected"""
        data = {
            "canvas_type": "generic",
            "component_type": "chart"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("chart_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_chart_invalid_type(self, validation_service):
        """Verify invalid chart_type is rejected"""
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "3d_surface"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is False
        assert any("chart_type" in error.lower() for error in result.errors)

    def test_validate_canvas_data_chart_valid_types(self, validation_service):
        """Verify all valid chart types are accepted"""
        valid_types = ["line", "bar", "pie", "scatter"]
        for chart_type in valid_types:
            data = {
                "canvas_type": "generic",
                "component_type": "chart",
                "chart_type": chart_type
            }
            result = validation_service.validate_canvas_data(data)
            assert result.is_valid, f"Chart type {chart_type} should be valid"


# =============================================================================
# TEST CLASS: Browser Action Validation
# =============================================================================

class TestBrowserActionValidation:
    """Tests for browser action validation"""

    def test_validate_browser_action_navigate_valid(self, validation_service):
        """Verify valid navigate action passes"""
        result = validation_service.validate_browser_action("navigate", {"url": "https://example.com"})
        assert result.is_valid is True

    def test_validate_browser_action_navigate_missing_url(self, validation_service):
        """Verify missing URL for navigate is rejected"""
        result = validation_service.validate_browser_action("navigate", {})
        assert result.is_valid is False
        assert any("url" in error.lower() for error in result.errors)

    def test_validate_browser_action_navigate_invalid_protocol(self, validation_service):
        """Verify invalid URL protocol is rejected"""
        result = validation_service.validate_browser_action("navigate", {"url": "ftp://example.com"})
        assert result.is_valid is False
        assert any("url" in error.lower() or "http" in error.lower() for error in result.errors)

    def test_validate_browser_action_click_valid(self, validation_service):
        """Verify valid click action passes"""
        result = validation_service.validate_browser_action("click", {"selector": "#button"})
        assert result.is_valid is True

    def test_validate_browser_action_click_missing_selector(self, validation_service):
        """Verify missing selector for click is rejected"""
        result = validation_service.validate_browser_action("click", {})
        assert result.is_valid is False
        assert any("selector" in error.lower() for error in result.errors)

    def test_validate_browser_action_fill_form_valid(self, validation_service):
        """Verify valid fill_form action passes"""
        result = validation_service.validate_browser_action("fill_form", {"selectors": {"name": "John"}})
        assert result.is_valid is True

    def test_validate_browser_action_fill_form_missing_selectors(self, validation_service):
        """Verify missing selectors for fill_form is rejected"""
        result = validation_service.validate_browser_action("fill_form", {})
        assert result.is_valid is False
        assert any("selectors" in error.lower() for error in result.errors)

    def test_validate_browser_action_fill_form_invalid_type(self, validation_service):
        """Verify non-dict selectors for fill_form is rejected"""
        result = validation_service.validate_browser_action("fill_form", {"selectors": "not_a_dict"})
        assert result.is_valid is False
        assert any("selectors" in error.lower() for error in result.errors)

    def test_validate_browser_action_screenshot_valid(self, validation_service):
        """Verify valid screenshot action passes"""
        result = validation_service.validate_browser_action("screenshot", {"session_id": "session-123"})
        assert result.is_valid is True

    def test_validate_browser_action_screenshot_missing_session(self, validation_service):
        """Verify missing session_id for screenshot is rejected"""
        result = validation_service.validate_browser_action("screenshot", {})
        assert result.is_valid is False
        assert any("session_id" in error.lower() for error in result.errors)

    def test_validate_browser_action_execute_script_valid(self, validation_service):
        """Verify valid execute_script action passes"""
        result = validation_service.validate_browser_action("execute_script", {"script": "console.log('test')"})
        assert result.is_valid is True

    def test_validate_browser_action_execute_script_missing_script(self, validation_service):
        """Verify missing script is rejected"""
        result = validation_service.validate_browser_action("execute_script", {})
        assert result.is_valid is False
        assert any("script" in error.lower() for error in result.errors)

    def test_validate_browser_action_execute_script_empty_script(self, validation_service):
        """Verify empty script is rejected"""
        result = validation_service.validate_browser_action("execute_script", {"script": "   "})
        assert result.is_valid is False
        assert any("script" in error.lower() or "empty" in error.lower() for error in result.errors)


# =============================================================================
# TEST CLASS: Device Action Validation
# =============================================================================

class TestDeviceActionValidation:
    """Tests for device action validation"""

    def test_validate_device_action_camera_snap_valid(self, validation_service):
        """Verify valid camera_snap action passes"""
        result = validation_service.validate_device_action("camera_snap", {"device_node_id": "device-123"})
        assert result.is_valid is True

    def test_validate_device_action_camera_snap_missing_device(self, validation_service):
        """Verify missing device_node_id for camera is rejected"""
        result = validation_service.validate_device_action("camera_snap", {})
        assert result.is_valid is False
        assert any("device_node_id" in error.lower() for error in result.errors)

    def test_validate_device_action_screen_record_valid(self, validation_service):
        """Verify valid screen_record_start action passes"""
        result = validation_service.validate_device_action("screen_record_start", {
            "device_node_id": "device-123",
            "duration_seconds": 60
        })
        assert result.is_valid is True

    def test_validate_device_action_screen_record_invalid_duration_low(self, validation_service):
        """Verify duration below 1 is rejected"""
        result = validation_service.validate_device_action("screen_record_start", {
            "device_node_id": "device-123",
            "duration_seconds": 0
        })
        assert result.is_valid is False
        assert any("duration" in error.lower() for error in result.errors)

    def test_validate_device_action_screen_record_invalid_duration_high(self, validation_service):
        """Verify duration above 3600 is rejected"""
        result = validation_service.validate_device_action("screen_record_start", {
            "device_node_id": "device-123",
            "duration_seconds": 4000
        })
        assert result.is_valid is False
        assert any("duration" in error.lower() for error in result.errors)

    def test_validate_device_action_screen_record_missing_device(self, validation_service):
        """Verify missing device_node_id for screen recording is rejected"""
        result = validation_service.validate_device_action("screen_record_start", {"duration_seconds": 60})
        assert result.is_valid is False
        assert any("device_node_id" in error.lower() for error in result.errors)

    def test_validate_device_action_get_location_valid(self, validation_service):
        """Verify valid get_location action passes"""
        result = validation_service.validate_device_action("get_location", {"device_node_id": "device-123"})
        assert result.is_valid is True

    def test_validate_device_action_send_notification_valid(self, validation_service):
        """Verify valid send_notification action passes"""
        result = validation_service.validate_device_action("send_notification", {
            "device_node_id": "device-123",
            "message": "Test notification"
        })
        assert result.is_valid is True

    def test_validate_device_action_send_notification_missing_device(self, validation_service):
        """Verify missing device_node_id for notification is rejected"""
        result = validation_service.validate_device_action("send_notification", {"message": "Test"})
        assert result.is_valid is False
        assert any("device_node_id" in error.lower() for error in result.errors)

    def test_validate_device_action_send_notification_missing_message(self, validation_service):
        """Verify missing message for notification is rejected"""
        result = validation_service.validate_device_action("send_notification", {"device_node_id": "device-123"})
        assert result.is_valid is False
        assert any("message" in error.lower() for error in result.errors)

    def test_validate_device_action_execute_command_valid(self, validation_service):
        """Verify valid execute_command action passes"""
        result = validation_service.validate_device_action("execute_command", {
            "device_node_id": "device-123",
            "command": "ls -la"
        })
        assert result.is_valid is True

    def test_validate_device_action_execute_command_missing_device(self, validation_service):
        """Verify missing device_node_id for command execution is rejected"""
        result = validation_service.validate_device_action("execute_command", {"command": "ls"})
        assert result.is_valid is False
        assert any("device_node_id" in error.lower() for error in result.errors)

    def test_validate_device_action_execute_command_missing_command(self, validation_service):
        """Verify missing command is rejected"""
        result = validation_service.validate_device_action("execute_command", {"device_node_id": "device-123"})
        assert result.is_valid is False
        assert any("command" in error.lower() for error in result.errors)

    def test_validate_device_action_execute_command_too_long(self, validation_service):
        """Verify command too long is rejected"""
        long_command = "a" * 1001
        result = validation_service.validate_device_action("execute_command", {
            "device_node_id": "device-123",
            "command": long_command
        })
        assert result.is_valid is False
        assert any("too long" in error.lower() for error in result.errors)

    def test_validate_device_action_execute_command_dangerous(self, validation_service):
        """Verify dangerous commands are rejected"""
        dangerous_commands = [
            "rm -rf /",
            "format c:",
            "del /f /q c:\\*",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda"
        ]
        for cmd in dangerous_commands:
            result = validation_service.validate_device_action("execute_command", {
                "device_node_id": "device-123",
                "command": cmd
            })
            assert result.is_valid is False, f"Command '{cmd}' should be rejected"
            assert any("dangerous" in error.lower() for error in result.errors)


# =============================================================================
# TEST CLASS: Execution Request Validation
# =============================================================================

class TestExecutionRequestValidation:
    """Tests for execution request validation"""

    def test_validate_execution_request_valid(self, validation_service):
        """Verify valid execution request passes"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello world"
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is True

    def test_validate_execution_request_missing_agent_id(self, validation_service):
        """Verify missing agent_id is rejected"""
        request = {"message": "Hello"}
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("agent_id" in error.lower() for error in result.errors)

    def test_validate_execution_request_missing_message(self, validation_service):
        """Verify missing message is rejected"""
        request = {"agent_id": "agent-123"}
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("message" in error.lower() for error in result.errors)

    def test_validate_execution_request_empty_message(self, validation_service):
        """Verify empty message is rejected"""
        request = {
            "agent_id": "agent-123",
            "message": "   "
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("message" in error.lower() and ("empty" in error.lower() or "cannot be empty" in error.lower()) for error in result.errors)

    def test_validate_execution_request_message_too_long(self, validation_service):
        """Verify message too long is rejected"""
        long_message = "a" * 100001
        request = {
            "agent_id": "agent-123",
            "message": long_message
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("too long" in error.lower() for error in result.errors)

    def test_validate_execution_request_invalid_message_type(self, validation_service):
        """Verify non-string message is rejected"""
        request = {
            "agent_id": "agent-123",
            "message": 123
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("message" in error.lower() and "string" in error.lower() for error in result.errors)

    def test_validate_execution_request_invalid_session_id_empty(self, validation_service):
        """Verify empty session_id is rejected"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello",
            "session_id": ""
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("session_id" in error.lower() for error in result.errors)

    def test_validate_execution_request_invalid_session_id_type(self, validation_service):
        """Verify non-string session_id is rejected"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello",
            "session_id": 123
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("session_id" in error.lower() for error in result.errors)

    def test_validate_execution_request_valid_session_id(self, validation_service):
        """Verify valid session_id is accepted"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello",
            "session_id": "session-abc-123"
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is True

    def test_validate_execution_request_streaming_invalid_max_tokens(self, validation_service):
        """Verify invalid max_tokens with streaming is rejected"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello",
            "stream": True,
            "max_tokens": 0
        }
        result = validation_service.validate_execution_request(request)
        assert result.is_valid is False
        assert any("max_tokens" in error.lower() for error in result.errors)


# =============================================================================
# TEST CLASS: Bulk Operation Validation
# =============================================================================

class TestBulkOperationValidation:
    """Tests for bulk operation validation"""

    def test_validate_bulk_operation_insert_valid(self, validation_service):
        """Verify valid insert operation passes"""
        items = [{"id": "1", "name": "Item 1"}]
        result = validation_service.validate_bulk_operation("insert", items)
        assert result.is_valid is True

    def test_validate_bulk_operation_invalid_operation_type(self, validation_service):
        """Verify invalid operation type is rejected"""
        items = [{"id": "1"}]
        result = validation_service.validate_bulk_operation("invalid_op", items)
        assert result.is_valid is False
        assert any("invalid operation" in error.lower() or "operation" in error.lower() for error in result.errors)

    def test_validate_bulk_operation_valid_operations(self, validation_service):
        """Verify all valid operation types are accepted"""
        valid_ops = ["insert", "update", "delete"]
        for op in valid_ops:
            result = validation_service.validate_bulk_operation(op, [{"id": "1"}])
            assert result.is_valid, f"Operation {op} should be valid"

    def test_validate_bulk_operation_items_not_list(self, validation_service):
        """Verify non-list items are rejected"""
        result = validation_service.validate_bulk_operation("insert", {"id": "1"})
        assert result.is_valid is False
        assert any("items must be a list" in error.lower() or "list" in error.lower() for error in result.errors)

    def test_validate_bulk_operation_items_empty(self, validation_service):
        """Verify empty items list is rejected"""
        result = validation_service.validate_bulk_operation("insert", [])
        assert result.is_valid is False
        assert any("cannot be empty" in error.lower() or "empty" in error.lower() for error in result.errors)

    def test_validate_bulk_operation_items_too_many(self, validation_service):
        """Verify too many items are rejected"""
        items = [{"id": str(i)} for i in range(1001)]
        result = validation_service.validate_bulk_operation("insert", items)
        assert result.is_valid is False
        assert any("1000" in error.lower() or "more than" in error.lower() for error in result.errors)

    def test_validate_bulk_operation_insert_item_not_dict(self, validation_service):
        """Verify non-dict item in insert is rejected"""
        items = [{"id": "1"}, "not_a_dict", {"id": "2"}]
        result = validation_service.validate_bulk_operation("insert", items)
        assert result.is_valid is False
        assert any("must be a dictionary" in error.lower() or "dictionary" in error.lower() for error in result.errors)

    def test_validate_bulk_operation_insert_item_missing_fields(self, validation_service):
        """Verify item missing id and name is flagged"""
        items = [{"value": "test"}]
        result = validation_service.validate_bulk_operation("insert", items)
        # Should flag issue with first 5 items
        assert not result.is_valid or len(result.errors) > 0


# =============================================================================
# TEST CLASS: Pydantic Model Validation
# =============================================================================

class TestPydanticModels:
    """Tests for Pydantic model validation"""

    def test_agent_config_model_valid(self, sample_agent_config):
        """Verify valid agent config passes Pydantic validation"""
        model = AgentConfigModel(**sample_agent_config)
        assert model.name == "Test Agent"
        assert model.domain == "customer_support"
        assert model.maturity_level == "INTERN"
        assert model.temperature == 0.7
        assert model.max_tokens == 2000

    def test_agent_config_model_empty_name_raises_error(self):
        """Verify empty name raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="", domain="customer_support")
        assert "name" in str(exc_info.value).lower()

    def test_agent_config_model_invalid_domain_raises_error(self):
        """Verify invalid domain raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="invalid")
        assert "domain" in str(exc_info.value).lower()

    def test_agent_config_model_invalid_temperature_raises_error(self):
        """Verify invalid temperature raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="customer_support", temperature=3.0)
        assert "temperature" in str(exc_info.value).lower()

    def test_canvas_data_model_valid(self, sample_canvas_data):
        """Verify valid canvas data passes Pydantic validation"""
        model = CanvasDataModel(**sample_canvas_data)
        assert model.canvas_type == "generic"
        assert model.component_type == "chart"
        assert model.chart_type == "line"

    def test_canvas_data_model_invalid_canvas_type_raises_error(self):
        """Verify invalid canvas_type raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            CanvasDataModel(canvas_type="invalid", component_type="chart")
        assert "canvas_type" in str(exc_info.value).lower()

    def test_execution_request_model_valid(self):
        """Verify valid execution request passes Pydantic validation"""
        data = {
            "agent_id": "agent-123",
            "message": "Hello world",
            "session_id": "session-456",
            "stream": True,
            "max_tokens": 1000
        }
        model = ExecutionRequestModel(**data)
        assert model.agent_id == "agent-123"
        assert model.message == "Hello world"
        assert model.stream is True
        assert model.max_tokens == 1000

    def test_execution_request_model_empty_agent_id_raises_error(self):
        """Verify empty agent_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="", message="Hello")
        assert "agent_id" in str(exc_info.value).lower()

    def test_execution_request_model_empty_message_raises_error(self):
        """Verify empty message raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message="")
        assert "message" in str(exc_info.value).lower()

    def test_execution_request_model_message_too_long_raises_error(self):
        """Verify message too long raises ValidationError"""
        long_message = "a" * 100001
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message=long_message)
        assert "message" in str(exc_info.value).lower()

    def test_execution_request_model_invalid_max_tokens_raises_error(self):
        """Verify invalid max_tokens raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message="Hello", max_tokens=0)
        assert "max_tokens" in str(exc_info.value).lower()


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================

class TestValidationServiceEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_validate_agent_config_extra_fields_ignored(self, validation_service):
        """Verify extra fields are ignored (no errors raised)"""
        config = {
            "name": "Test",
            "domain": "customer_support",
            "extra_field": "value",
            "another_extra": 123
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is True

    def test_validate_canvas_data_extra_fields_ignored(self, validation_service):
        """Verify extra canvas fields are ignored"""
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "line",
            "custom_field": "value"
        }
        result = validation_service.validate_canvas_data(data)
        assert result.is_valid is True

    def test_validate_browser_action_unknown_action_passes(self, validation_service):
        """Verify unknown browser action passes (no validation errors)"""
        result = validation_service.validate_browser_action("unknown_action", {})
        assert result.is_valid is True

    def test_validate_device_action_unknown_action_passes(self, validation_service):
        """Verify unknown device action passes (no validation errors)"""
        result = validation_service.validate_device_action("unknown_action", {})
        assert result.is_valid is True

    def test_multiple_validation_errors_aggregated(self, validation_service):
        """Verify multiple errors are aggregated"""
        config = {
            # Missing name
            "domain": "invalid_domain",
            "maturity_level": "INVALID",
            "temperature": 5.0
        }
        result = validation_service.validate_agent_config(config)
        assert result.is_valid is False
        assert len(result.errors) >= 3  # At least 3 errors
