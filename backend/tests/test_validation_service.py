"""
Test Validation Service

Tests for the centralized validation service.
"""

import pytest
from core.validation_service import (
    ValidationService,
    ValidationResult,
    AgentConfigModel,
    CanvasDataModel,
    ExecutionRequestModel
)
from pydantic import ValidationError as PydanticValidationError


class TestValidationResult:
    """Test suite for ValidationResult"""

    def test_success_result(self):
        """Test creating successful validation result"""
        result = ValidationResult.success()

        assert result.is_valid is True
        assert result.errors == []
        assert result.details == {}

    def test_single_error(self):
        """Test creating error result with single message"""
        result = ValidationResult.error("Invalid input")

        assert result.is_valid is False
        assert result.errors == ["Invalid input"]

    def test_multiple_errors(self):
        """Test creating error result with multiple messages"""
        result = ValidationResult.multiple(["Error 1", "Error 2"])

        assert result.is_valid is False
        assert len(result.errors) == 2


class TestValidationService:
    """Test suite for ValidationService"""

    @pytest.fixture
    def service(self):
        """Create validation service instance"""
        return ValidationService()

    def test_validate_agent_config_valid(self, service):
        """Test validation of valid agent config"""
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INTERN"
        }

        result = service.validate_agent_config(config)

        assert result.is_valid is True

    def test_validate_agent_config_missing_name(self, service):
        """Test validation fails when name is missing"""
        config = {
            "domain": "customer_support",
            "maturity_level": "INTERN"
        }

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "name" in str(result.errors).lower()

    def test_validate_agent_config_invalid_domain(self, service):
        """Test validation fails with invalid domain"""
        config = {
            "name": "Test Agent",
            "domain": "invalid_domain",
            "maturity_level": "INTERN"
        }

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert "Invalid domain" in str(result.errors)

    def test_validate_canvas_data_valid(self, service):
        """Test validation of valid canvas data"""
        data = {
            "canvas_type": "generic",
            "component_type": "chart",
            "chart_type": "line"
        }

        result = service.validate_canvas_data(data)

        assert result.is_valid is True

    def test_validate_canvas_data_missing_type(self, service):
        """Test validation fails when canvas_type is missing"""
        data = {
            "component_type": "chart"
        }

        result = service.validate_canvas_data(data)

        assert result.is_valid is False
        assert "canvas_type" in str(result.errors).lower()

    def test_validate_browser_action_navigate(self, service):
        """Test validation of navigate action"""
        params = {
            "url": "https://example.com"
        }

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is True

    def test_validate_browser_action_navigate_missing_url(self, service):
        """Test validation fails when URL is missing"""
        params = {}

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is False
        assert "URL" in str(result.errors)

    def test_validate_browser_action_navigate_invalid_url(self, service):
        """Test validation fails with invalid URL"""
        params = {
            "url": "invalid-url"
        }

        result = service.validate_browser_action("navigate", params)

        assert result.is_valid is False
        assert "URL must start with" in str(result.errors)

    def test_validate_device_action_camera(self, service):
        """Test validation of camera action"""
        params = {
            "device_node_id": "device-123"
        }

        result = service.validate_device_action("camera_snap", params)

        assert result.is_valid is True

    def test_validate_device_action_command_dangerous(self, service):
        """Test validation blocks dangerous commands"""
        params = {
            "device_node_id": "device-123",
            "command": "rm -rf /"
        }

        result = service.validate_device_action("execute_command", params)

        assert result.is_valid is False
        assert "dangerous" in str(result.errors).lower()

    def test_validate_execution_request_valid(self, service):
        """Test validation of valid execution request"""
        request = {
            "agent_id": "agent-123",
            "message": "Hello, world!"
        }

        result = service.validate_execution_request(request)

        assert result.is_valid is True

    def test_validate_execution_request_missing_agent_id(self, service):
        """Test validation fails when agent_id is missing"""
        request = {
            "message": "Test"
        }

        result = service.validate_execution_request(request)

        assert result.is_valid is False
        assert "agent_id" in str(result.errors).lower()


class TestPydanticModels:
    """Test suite for Pydantic validation models"""

    def test_agent_config_model_valid(self):
        """Test AgentConfigModel with valid data"""
        data = {
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INTERN"
        }

        model = AgentConfigModel(**data)

        assert model.name == "Test Agent"
        assert model.domain == "customer_support"
        assert model.maturity_level == "INTERN"

    def test_agent_config_model_invalid_domain(self):
        """Test AgentConfigModel rejects invalid domain"""
        data = {
            "name": "Test Agent",
            "domain": "invalid_domain",
            "maturity_level": "INTERN"
        }

        with pytest.raises(PydanticValidationError) as exc_info:
            AgentConfigModel(**data)

        assert "Invalid domain" in str(exc_info.value)

    def test_canvas_data_model_valid(self):
        """Test CanvasDataModel with valid data"""
        data = {
            "canvas_type": "generic",
            "component_type": "chart"
        }

        model = CanvasDataModel(**data)

        assert model.canvas_type == "generic"
        assert model.component_type == "chart"

    def test_execution_request_model_valid(self):
        """Test ExecutionRequestModel with valid data"""
        data = {
            "agent_id": "agent-123",
            "message": "Test message"
        }

        model = ExecutionRequestModel(**data)

        assert model.agent_id == "agent-123"
        assert model.message == "Test message"

    def test_execution_request_model_message_too_long(self):
        """Test ExecutionRequestModel rejects too-long messages"""
        data = {
            "agent_id": "agent-123",
            "message": "x" * 100001  # Exceeds limit
        }

        with pytest.raises(PydanticValidationError) as exc_info:
            ExecutionRequestModel(**data)

        assert "too long" in str(exc_info.value).lower() or "length" in str(exc_info.value).lower()
