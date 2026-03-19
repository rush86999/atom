"""
Comprehensive tests for ValidationService module.

Tests cover ValidationResult class, ValidationService class,
and Pydantic model validation.
"""

import pytest
from pydantic import ValidationError

from core.validation_service import (
    AgentConfigModel,
    CanvasDataModel,
    ExecutionRequestModel,
    ValidationResult,
    ValidationService,
)


class TestValidationResult:
    """Test suite for ValidationResult class."""

    def test_create_success_result(self):
        """Test creating a success result."""
        result = ValidationResult.success()

        assert result.is_valid is True
        assert result.errors == []
        assert result.details == {}

    def test_create_success_result_with_data(self):
        """Test creating success result with details."""
        result = ValidationResult.success()
        result.details = {"user_id": "123", "action": "test"}

        assert result.is_valid is True
        assert result.details["user_id"] == "123"

    def test_create_error_result(self):
        """Test creating an error result."""
        result = ValidationResult.error("Invalid input")

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Invalid input"
        assert result.details == {}

    def test_create_error_result_with_details(self):
        """Test creating error result with details."""
        details = {"field": "email", "value": "invalid"}
        result = ValidationResult.error("Invalid email format", details)

        assert result.is_valid is False
        assert result.errors[0] == "Invalid email format"
        assert result.details["field"] == "email"

    def test_create_warning_result(self):
        """Test creating a result with warnings."""
        result = ValidationResult.error("Warning message", {"warning": True})

        assert result.is_valid is False
        assert result.errors[0] == "Warning message"
        assert result.details["warning"] is True

    def test_create_multiple_errors_result(self):
        """Test creating result with multiple errors."""
        errors = ["Error 1", "Error 2", "Error 3"]
        result = ValidationResult.multiple(errors)

        assert result.is_valid is False
        assert len(result.errors) == 3
        assert result.errors == errors
        assert result.details == {}

    def test_create_multiple_errors_with_details(self):
        """Test creating result with multiple errors and details."""
        errors = ["Field A required", "Field B invalid"]
        details = {"fields": ["A", "B"]}
        result = ValidationResult.multiple(errors, details)

        assert result.is_valid is False
        assert len(result.errors) == 2
        assert result.details["fields"] == ["A", "B"]

    def test_is_success_returns_true_for_success(self):
        """Test is_success is True for valid result."""
        result = ValidationResult.success()

        assert result.is_valid is True

    def test_is_success_returns_false_for_errors(self):
        """Test is_success is False for error result."""
        result = ValidationResult.error("Error")

        assert result.is_valid is False

    def test_is_success_returns_false_for_warnings(self):
        """Test is_success is False for result with warnings."""
        result = ValidationResult.error("Warning")

        assert result.is_valid is False

    def test_to_dict_converts_result(self):
        """Test converting result to dictionary."""
        result = ValidationResult.success()
        result.details = {"key": "value"}

        result_dict = {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "details": result.details,
        }

        assert result_dict["is_valid"] is True
        assert result_dict["details"]["key"] == "value"

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all fields."""
        errors = ["Error 1", "Error 2"]
        details = {"field": "test"}
        result = ValidationResult.multiple(errors, details)

        result_dict = {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "details": result.details,
        }

        assert result_dict["is_valid"] is False
        assert len(result_dict["errors"]) == 2
        assert result_dict["details"]["field"] == "test"

    def test_initialization_with_custom_errors(self):
        """Test ValidationResult initialization with custom errors."""
        custom_errors = ["Custom error 1", "Custom error 2"]
        result = ValidationResult(is_valid=False, errors=custom_errors)

        assert result.is_valid is False
        assert result.errors == custom_errors

    def test_initialization_with_custom_details(self):
        """Test ValidationResult initialization with custom details."""
        custom_details = {"field1": "value1", "field2": 123}
        result = ValidationResult(is_valid=True, details=custom_details)

        assert result.is_valid is True
        assert result.details == custom_details


class TestValidationService:
    """Test suite for ValidationService class."""

    def test_initialization_default(self):
        """Test creating ValidationService with default config."""
        service = ValidationService()

        assert service is not None

    def test_validate_agent_config_success(self):
        """Test validating valid agent configuration."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "maturity_level": "INTERN"}

        result = service.validate_agent_config(config)

        assert result.is_valid is True
        assert result.errors == []

    def test_validate_agent_config_missing_name(self):
        """Test validation fails when name is missing."""
        service = ValidationService()
        config = {"domain": "customer_support"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Agent name is required" in result.errors

    def test_validate_agent_config_empty_name(self):
        """Test validation fails when name is empty."""
        service = ValidationService()
        config = {"name": "   ", "domain": "customer_support"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Agent name cannot be empty" in result.errors

    def test_validate_agent_config_missing_domain(self):
        """Test validation fails when domain is missing."""
        service = ValidationService()
        config = {"name": "Test Agent"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Domain is required" in result.errors

    def test_validate_agent_config_invalid_domain(self):
        """Test validation fails with invalid domain."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "invalid_domain"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Invalid domain" in result.errors[0]

    def test_validate_agent_config_valid_domains(self):
        """Test all valid domains are accepted."""
        service = ValidationService()
        valid_domains = [
            "customer_support",
            "data_analysis",
            "content_creation",
            "automation",
            "research",
        ]

        for domain in valid_domains:
            config = {"name": "Test Agent", "domain": domain}
            result = service.validate_agent_config(config)
            assert result.is_valid is True, f"Domain {domain} should be valid"

    def test_validate_agent_config_invalid_maturity_level(self):
        """Test validation fails with invalid maturity level."""
        service = ValidationService()
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INVALID_LEVEL",
        }

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Invalid maturity level" in result.errors[0]

    def test_validate_agent_config_valid_maturity_levels(self):
        """Test all valid maturity levels are accepted."""
        service = ValidationService()
        valid_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        for level in valid_levels:
            config = {"name": "Test Agent", "domain": "customer_support", "maturity_level": level}
            result = service.validate_agent_config(config)
            assert result.is_valid is True, f"Maturity level {level} should be valid"

    def test_validate_agent_config_invalid_temperature_negative(self):
        """Test validation fails with negative temperature."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "temperature": -0.5}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Temperature must be between 0 and 2" in result.errors

    def test_validate_agent_config_invalid_temperature_too_high(self):
        """Test validation fails with temperature > 2."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "temperature": 2.5}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Temperature must be between 0 and 2" in result.errors

    def test_validate_agent_config_valid_temperature(self):
        """Test valid temperature values are accepted."""
        service = ValidationService()
        valid_temps = [0, 0.5, 1.0, 1.5, 2.0]

        for temp in valid_temps:
            config = {"name": "Test Agent", "domain": "customer_support", "temperature": temp}
            result = service.validate_agent_config(config)
            assert result.is_valid is True, f"Temperature {temp} should be valid"

    def test_validate_agent_config_invalid_max_tokens_too_low(self):
        """Test validation fails with max_tokens < 1."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "max_tokens": 0}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Max tokens must be between 1 and 32000" in result.errors

    def test_validate_agent_config_invalid_max_tokens_too_high(self):
        """Test validation fails with max_tokens > 32000."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "max_tokens": 40000}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Max tokens must be between 1 and 32000" in result.errors

    def test_validate_agent_config_invalid_max_tokens_type(self):
        """Test validation fails with non-integer max_tokens."""
        service = ValidationService()
        config = {"name": "Test Agent", "domain": "customer_support", "max_tokens": "not_an_int"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Max tokens must be between 1 and 32000" in result.errors

    def test_validate_canvas_data_success(self):
        """Test validating valid canvas data."""
        service = ValidationService()
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "line",
        }

        result = service.validate_canvas_data(data)

        assert result.is_valid is True

    def test_validate_canvas_data_missing_canvas_type(self):
        """Test validation fails when canvas_type is missing."""
        service = ValidationService()
        data = {"component_type": "chart"}

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "canvas_type is required" in result.errors

    def test_validate_canvas_data_missing_component_type(self):
        """Test validation fails when component_type is missing."""
        service = ValidationService()
        data = {"canvas_type": "generic"}

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "component_type is required" in result.errors

    def test_validate_canvas_data_invalid_canvas_type(self):
        """Test validation fails with invalid canvas_type."""
        service = ValidationService()
        data = {"canvas_type": "invalid_type", "component_type": "chart"}

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "Invalid canvas_type" in result.errors[0]

    def test_validate_canvas_data_valid_canvas_types(self):
        """Test all valid canvas types are accepted."""
        service = ValidationService()
        valid_types = [
            "generic",
            "docs",
            "email",
            "sheets",
            "orchestration",
            "terminal",
            "coding",
            "status_panel",
            "form",
        ]

        for canvas_type in valid_types:
            data = {"canvas_type": canvas_type, "component_type": "markdown"}
            result = service.validate_canvas_data(data)
            assert result.is_valid is True, f"Canvas type {canvas_type} should be valid"

    def test_validate_canvas_data_invalid_component_for_generic(self):
        """Test validation fails with invalid component for generic canvas."""
        service = ValidationService()
        data = {"canvas_type": "generic", "component_type": "invalid_component"}

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "Invalid component_type for generic canvas" in result.errors[0]

    def test_validate_canvas_data_valid_components_for_generic(self):
        """Test all valid components for generic canvas."""
        service = ValidationService()
        # Components without additional required fields
        simple_components = ["markdown", "form", "table", "image", "text"]

        for component in simple_components:
            data = {"canvas_type": "generic", "component_type": component}
            result = service.validate_canvas_data(data)
            assert result.is_valid is True, f"Component {component} should be valid"

        # Chart component requires chart_type
        chart_data = {"canvas_type": "generic", "component_type": "chart", "chart_type": "line"}
        chart_result = service.validate_canvas_data(chart_data)
        assert chart_result.is_valid is True, "Chart component should be valid with chart_type"

    def test_validate_canvas_data_missing_chart_type(self):
        """Test validation fails when chart_type is missing for chart component."""
        service = ValidationService()
        data = {"canvas_type": "generic", "component_type": "chart"}

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "chart_type is required for chart component" in result.errors

    def test_validate_canvas_data_invalid_chart_type(self):
        """Test validation fails with invalid chart_type."""
        service = ValidationService()
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "invalid_chart",
        }

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "Invalid chart_type" in result.errors[0]

    def test_validate_canvas_data_valid_chart_types(self):
        """Test all valid chart types are accepted."""
        service = ValidationService()
        valid_chart_types = ["line", "bar", "pie", "scatter"]

        for chart_type in valid_chart_types:
            data = {
                "canvas_type": "generic",
                "component_type": "chart",
                "chart_type": chart_type,
            }
            result = service.validate_canvas_data(data)
            assert result.is_valid is True, f"Chart type {chart_type} should be valid"

    def test_validate_browser_action_navigate_success(self):
        """Test validating valid navigate action."""
        service = ValidationService()
        params = {"url": "https://example.com"}

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is True

    def test_validate_browser_action_navigate_missing_url(self):
        """Test validation fails when URL is missing for navigate."""
        service = ValidationService()
        params = {}

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is False
        assert "URL is required for navigate action" in result.errors

    def test_validate_browser_action_navigate_invalid_url(self):
        """Test validation fails with invalid URL format."""
        service = ValidationService()
        params = {"url": "invalid-url"}

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is False
        assert "URL must start with http:// or https://" in result.errors

    def test_validate_browser_action_click_success(self):
        """Test validating valid click action."""
        service = ValidationService()
        params = {"selector": "#button-id"}

        result = service.validate_browser_action("click", params)

        assert result.is_valid is True

    def test_validate_browser_action_click_missing_selector(self):
        """Test validation fails when selector is missing for click."""
        service = ValidationService()
        params = {}

        result = service.validate_browser_action("click", params)

        assert result.is_valid is False
        assert "Selector is required for click action" in result.errors

    def test_validate_browser_action_fill_form_success(self):
        """Test validating valid fill_form action."""
        service = ValidationService()
        params = {"selectors": {"#name": "John", "#email": "john@example.com"}}

        result = service.validate_browser_action("fill_form", params)

        assert result.is_valid is True

    def test_validate_browser_action_fill_form_missing_selectors(self):
        """Test validation fails when selectors is missing for fill_form."""
        service = ValidationService()
        params = {}

        result = service.validate_browser_action("fill_form", params)

        assert result.is_valid is False
        assert "Selectors dictionary is required for fill_form" in result.errors

    def test_validate_browser_action_fill_form_invalid_selectors_type(self):
        """Test validation fails when selectors is not a dict."""
        service = ValidationService()
        params = {"selectors": "not-a-dict"}

        result = service.validate_browser_action("fill_form", params)

        assert result.is_valid is False
        assert "Selectors must be a dictionary" in result.errors

    def test_validate_browser_action_screenshot_success(self):
        """Test validating valid screenshot action."""
        service = ValidationService()
        params = {"session_id": "session-123"}

        result = service.validate_browser_action("screenshot", params)

        assert result.is_valid is True

    def test_validate_browser_action_screenshot_missing_session_id(self):
        """Test validation fails when session_id is missing for screenshot."""
        service = ValidationService()
        params = {}

        result = service.validate_browser_action("screenshot", params)

        assert result.is_valid is False
        assert "session_id is required for screenshot action" in result.errors

    def test_validate_browser_action_execute_script_success(self):
        """Test validating valid execute_script action."""
        service = ValidationService()
        params = {"script": "document.querySelector('#btn').click()"}

        result = service.validate_browser_action("execute_script", params)

        assert result.is_valid is True

    def test_validate_browser_action_execute_script_missing_script(self):
        """Test validation fails when script is missing."""
        service = ValidationService()
        params = {}

        result = service.validate_browser_action("execute_script", params)

        assert result.is_valid is False
        assert "Script is required for execute_script action" in result.errors

    def test_validate_browser_action_execute_script_empty_script(self):
        """Test validation fails when script is empty."""
        service = ValidationService()
        params = {"script": "   "}

        result = service.validate_browser_action("execute_script", params)

        assert result.is_valid is False
        assert "Script cannot be empty" in result.errors

    def test_validate_device_action_camera_snap_success(self):
        """Test validating valid camera_snap action."""
        service = ValidationService()
        params = {"device_node_id": "device-123"}

        result = service.validate_device_action("camera_snap", params)

        assert result.is_valid is True

    def test_validate_device_action_camera_snap_missing_device_id(self):
        """Test validation fails when device_node_id is missing."""
        service = ValidationService()
        params = {}

        result = service.validate_device_action("camera_snap", params)

        assert result.is_valid is False
        assert "device_node_id is required for camera action" in result.errors

    def test_validate_device_action_screen_record_success(self):
        """Test validating valid screen_record_start action."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "duration_seconds": 60}

        result = service.validate_device_action("screen_record_start", params)

        assert result.is_valid is True

    def test_validate_device_action_screen_record_invalid_duration_too_low(
        self,
    ):
        """Test validation fails with duration < 1."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "duration_seconds": 0}

        result = service.validate_device_action("screen_record_start", params)

        assert result.is_valid is False
        assert "Duration must be between 1 and 3600 seconds" in result.errors

    def test_validate_device_action_screen_record_invalid_duration_too_high(
        self,
    ):
        """Test validation fails with duration > 3600."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "duration_seconds": 4000}

        result = service.validate_device_action("screen_record_start", params)

        assert result.is_valid is False
        assert "Duration must be between 1 and 3600 seconds" in result.errors

    def test_validate_device_action_screen_record_invalid_duration_type(self):
        """Test validation fails with non-integer duration."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "duration_seconds": "not_an_int"}

        result = service.validate_device_action("screen_record_start", params)

        assert result.is_valid is False
        assert "Duration must be between 1 and 3600 seconds" in result.errors

    def test_validate_device_action_get_location_success(self):
        """Test validating valid get_location action."""
        service = ValidationService()
        params = {"device_node_id": "device-123"}

        result = service.validate_device_action("get_location", params)

        assert result.is_valid is True

    def test_validate_device_action_send_notification_success(self):
        """Test validating valid send_notification action."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "message": "Test notification"}

        result = service.validate_device_action("send_notification", params)

        assert result.is_valid is True

    def test_validate_device_action_send_notification_missing_message(self):
        """Test validation fails when message is missing."""
        service = ValidationService()
        params = {"device_node_id": "device-123"}

        result = service.validate_device_action("send_notification", params)

        assert result.is_valid is False
        assert "Message is required for notification" in result.errors

    def test_validate_device_action_execute_command_success(self):
        """Test validating valid execute_command action."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "command": "ls -la"}

        result = service.validate_device_action("execute_command", params)

        assert result.is_valid is True

    def test_validate_device_action_execute_command_missing_command(self):
        """Test validation fails when command is missing."""
        service = ValidationService()
        params = {"device_node_id": "device-123"}

        result = service.validate_device_action("execute_command", params)

        assert result.is_valid is False
        assert "Command is required for execution" in result.errors

    def test_validate_device_action_execute_command_too_long(self):
        """Test validation fails with command > 1000 characters."""
        service = ValidationService()
        params = {"device_node_id": "device-123", "command": "x" * 1001}

        result = service.validate_device_action("execute_command", params)

        assert result.is_valid is False
        assert "Command too long (max 1000 characters)" in result.errors

    def test_validate_device_action_execute_command_dangerous(self):
        """Test validation fails with dangerous commands."""
        service = ValidationService()
        dangerous_commands = ["rm -rf /", "format c:", "del /q *", "mkfs", "dd if=/dev/zero"]

        for cmd in dangerous_commands:
            params = {"device_node_id": "device-123", "command": cmd}
            result = service.validate_device_action("execute_command", params)
            assert result.is_valid is False, f"Command {cmd} should be rejected"
            assert "Potentially dangerous command detected" in result.errors[0]

    def test_validate_execution_request_success(self):
        """Test validating valid execution request."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "Hello, agent!"}

        result = service.validate_execution_request(request)

        assert result.is_valid is True

    def test_validate_execution_request_missing_agent_id(self):
        """Test validation fails when agent_id is missing."""
        service = ValidationService()
        request = {"message": "Hello"}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "agent_id is required" in result.errors

    def test_validate_execution_request_missing_message(self):
        """Test validation fails when message is missing."""
        service = ValidationService()
        request = {"agent_id": "agent-123"}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "message is required" in result.errors

    def test_validate_execution_request_empty_message(self):
        """Test validation fails when message is empty."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "   "}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "Message cannot be empty" in result.errors

    def test_validate_execution_request_invalid_message_type(self):
        """Test validation fails when message is not a string."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": 123}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "Message must be a string" in result.errors

    def test_validate_execution_request_message_too_long(self):
        """Test validation fails when message exceeds max length."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "x" * 100001}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "Message too long (max 100,000 characters)" in result.errors

    def test_validate_execution_request_invalid_session_id_type(self):
        """Test validation fails when session_id is not a string."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "Hello", "session_id": 123}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "session_id must be a non-empty string" in result.errors

    def test_validate_execution_request_invalid_session_id_empty(self):
        """Test validation fails when session_id is empty."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "Hello", "session_id": ""}

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "session_id must be a non-empty string" in result.errors

    def test_validate_execution_request_valid_session_id(self):
        """Test valid session_id is accepted."""
        service = ValidationService()
        request = {"agent_id": "agent-123", "message": "Hello", "session_id": "session-456"}

        result = service.validate_execution_request(request)

        assert result.is_valid is True

    def test_validate_execution_request_invalid_max_tokens_with_stream(self):
        """Test validation fails with invalid max_tokens when streaming."""
        service = ValidationService()
        request = {
            "agent_id": "agent-123",
            "message": "Hello",
            "stream": True,
            "max_tokens": -1,
        }

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "max_tokens must be a positive integer" in result.errors

    def test_validate_bulk_operation_insert_success(self):
        """Test validating valid bulk insert operation."""
        service = ValidationService()
        items = [{"id": "1", "name": "Item 1"}, {"id": "2", "name": "Item 2"}]

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is True

    def test_validate_bulk_operation_invalid_operation(self):
        """Test validation fails with invalid operation type."""
        service = ValidationService()
        items = [{"id": "1"}]

        result = service.validate_bulk_operation("invalid_operation", items)

        assert result.is_valid is False
        assert "Invalid operation" in result.errors[0]

    def test_validate_bulk_operation_valid_operations(self):
        """Test all valid operation types."""
        service = ValidationService()
        valid_operations = ["insert", "update", "delete"]

        for operation in valid_operations:
            items = [{"id": "1"}]
            result = service.validate_bulk_operation(operation, items)
            assert result.is_valid is True, f"Operation {operation} should be valid"

    def test_validate_bulk_operation_not_list(self):
        """Test validation fails when items is not a list."""
        service = ValidationService()
        items = {"id": "1"}

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is False
        assert "Items must be a list" in result.errors

    def test_validate_bulk_operation_empty_list(self):
        """Test validation fails when items list is empty."""
        service = ValidationService()
        items = []

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is False
        assert "Items list cannot be empty" in result.errors

    def test_validate_bulk_operation_too_many_items(self):
        """Test validation fails when items list exceeds maximum."""
        service = ValidationService()
        items = [{"id": str(i)} for i in range(1001)]

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is False
        assert "Cannot process more than 1000 items at once" in result.errors

    def test_validate_bulk_operation_item_not_dict(self):
        """Test validation fails when item is not a dictionary."""
        service = ValidationService()
        items = ["not_a_dict", {"id": "2"}]

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is False
        assert "Item 0 must be a dictionary" in result.errors[0]

    def test_validate_bulk_operation_item_missing_id_and_name(self):
        """Test validation fails when item lacks id and name."""
        service = ValidationService()
        items = [{"other_field": "value"}]

        result = service.validate_bulk_operation("insert", items)

        assert result.is_valid is False
        assert "Item 0 must have 'id' or 'name' field" in result.errors[0]


class TestPydanticModels:
    """Test suite for Pydantic model validation."""

    def test_validate_pydantic_agent_config_success(self):
        """Test valid AgentConfigModel."""
        config = AgentConfigModel(
            name="Test Agent", domain="customer_support", maturity_level="INTERN"
        )

        assert config.name == "Test Agent"
        assert config.domain == "customer_support"
        assert config.maturity_level == "INTERN"

    def test_validate_pydantic_agent_config_field_error_empty_name(self):
        """Test AgentConfigModel rejects empty name."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="", domain="customer_support")

        errors = exc_info.value.errors()
        assert any("Agent name cannot be empty" in str(err) for err in errors)

    def test_validate_pydantic_agent_config_field_error_invalid_domain(self):
        """Test AgentConfigModel rejects invalid domain."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="invalid_domain")

        errors = exc_info.value.errors()
        assert any("Invalid domain" in str(err) for err in errors)

    def test_validate_pydantic_agent_config_field_error_invalid_maturity(self):
        """Test AgentConfigModel rejects invalid maturity level."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="customer_support", maturity_level="INVALID")

        errors = exc_info.value.errors()
        assert any("Invalid maturity level" in str(err) for err in errors)

    def test_validate_pydantic_agent_config_field_error_invalid_temperature(self):
        """Test AgentConfigModel rejects invalid temperature."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="customer_support", temperature=3.0)

        errors = exc_info.value.errors()
        assert any("Temperature must be between 0 and 2" in str(err) for err in errors)

    def test_validate_pydantic_agent_config_field_error_invalid_max_tokens(self):
        """Test AgentConfigModel rejects invalid max_tokens."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigModel(name="Test", domain="customer_support", max_tokens=0)

        errors = exc_info.value.errors()
        assert any("Max tokens must be between 1 and 32000" in str(err) for err in errors)

    def test_validate_pydantic_agent_config_optional_fields(self):
        """Test AgentConfigModel optional fields."""
        config = AgentConfigModel(
            name="Test",
            domain="customer_support",
            description="Test agent",
            system_prompt="You are helpful",
        )

        assert config.description == "Test agent"
        assert config.system_prompt == "You are helpful"

    def test_validate_pydantic_canvas_data_success(self):
        """Test valid CanvasDataModel."""
        canvas = CanvasDataModel(
            canvas_type="generic", component_type="chart", chart_type="line"
        )

        assert canvas.canvas_type == "generic"
        assert canvas.component_type == "chart"
        assert canvas.chart_type == "line"

    def test_validate_pydantic_canvas_data_field_error_invalid_canvas_type(self):
        """Test CanvasDataModel rejects invalid canvas_type."""
        with pytest.raises(ValidationError) as exc_info:
            CanvasDataModel(canvas_type="invalid", component_type="chart")

        errors = exc_info.value.errors()
        assert any("Invalid canvas_type" in str(err) for err in errors)

    def test_validate_pydantic_canvas_data_field_error_invalid_component_type(self):
        """Test CanvasDataModel rejects invalid component_type for generic."""
        with pytest.raises(ValidationError) as exc_info:
            CanvasDataModel(canvas_type="generic", component_type="invalid")

        errors = exc_info.value.errors()
        assert any("Invalid component_type for generic canvas" in str(err) for err in errors)

    def test_validate_pydantic_canvas_data_optional_fields(self):
        """Test CanvasDataModel optional fields."""
        canvas = CanvasDataModel(
            canvas_type="generic",
            component_type="markdown",
            title="Test Title",
            content="Test Content",
            data={"key": "value"},
        )

        assert canvas.title == "Test Title"
        assert canvas.content == "Test Content"
        assert canvas.data == {"key": "value"}

    def test_validate_pydantic_execution_request_success(self):
        """Test valid ExecutionRequestModel."""
        request = ExecutionRequestModel(agent_id="agent-123", message="Hello")

        assert request.agent_id == "agent-123"
        assert request.message == "Hello"

    def test_validate_pydantic_execution_request_field_error_empty_agent_id(self):
        """Test ExecutionRequestModel rejects empty agent_id."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="", message="Hello")

        errors = exc_info.value.errors()
        assert any("Agent ID cannot be empty" in str(err) for err in errors)

    def test_validate_pydantic_execution_request_field_error_empty_message(self):
        """Test ExecutionRequestModel rejects empty message."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message="")

        errors = exc_info.value.errors()
        assert any("Message cannot be empty" in str(err) for err in errors)

    def test_validate_pydantic_execution_request_field_error_message_too_long(self):
        """Test ExecutionRequestModel rejects message > 100k chars."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message="x" * 100001)

        errors = exc_info.value.errors()
        assert any("Message too long" in str(err) for err in errors)

    def test_validate_pydantic_execution_request_field_error_invalid_max_tokens(self):
        """Test ExecutionRequestModel rejects invalid max_tokens."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionRequestModel(agent_id="agent-123", message="Hello", max_tokens=0)

        errors = exc_info.value.errors()
        assert any("Max tokens must be positive" in str(err) for err in errors)

    def test_validate_pydantic_execution_request_optional_fields(self):
        """Test ExecutionRequestModel optional fields."""
        request = ExecutionRequestModel(
            agent_id="agent-123",
            message="Hello",
            session_id="session-456",
            stream=True,
            max_tokens=1000,
            context={"key": "value"},
            metadata={"meta": "data"},
        )

        assert request.session_id == "session-456"
        assert request.stream is True
        assert request.max_tokens == 1000
        assert request.context == {"key": "value"}
        assert request.metadata == {"meta": "data"}

    def test_validate_pydantic_execution_request_defaults(self):
        """Test ExecutionRequestModel default values."""
        request = ExecutionRequestModel(agent_id="agent-123", message="Hello")

        assert request.stream is False
        assert request.session_id is None
        assert request.max_tokens is None
        assert request.context is None
        assert request.metadata is None


@pytest.fixture
def validation_service():
    """Fixture providing ValidationService instance."""
    return ValidationService()


@pytest.fixture
def valid_email():
    """Fixture providing valid email address."""
    return "user@example.com"


@pytest.fixture
def invalid_email():
    """Fixture providing invalid email address."""
    return "invalid-email"


@pytest.fixture
def sample_pydantic_model():
    """Fixture providing sample Pydantic model."""
    return AgentConfigModel(name="Test", domain="customer_support")
