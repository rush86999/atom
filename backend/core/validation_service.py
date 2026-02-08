"""
Validation Service for Atom Platform

Provides centralized input validation with Pydantic models and validation logic.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError, field_validator


logger = logging.getLogger(__name__)


class ValidationResult:
    """
    Result of a validation operation.

    Args:
        is_valid: Whether validation passed
        errors: List of error messages
        details: Additional error details

    Example:
        result = ValidationResult.success()
        result = ValidationResult.error(["Name is required", "Email invalid"])
    """

    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None, details: Optional[Dict[str, Any]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.details = details or {}

    @staticmethod
    def success() -> 'ValidationResult':
        """Create a successful validation result"""
        return ValidationResult(is_valid=True)

    @staticmethod
    def error(message: str, details: Optional[Dict[str, Any]] = None) -> 'ValidationResult':
        """Create a failed validation result"""
        return ValidationResult(
            is_valid=False,
            errors=[message],
            details=details or {}
        )

    @staticmethod
    def multiple(errors: List[str], details: Optional[Dict[str, Any]] = None) -> 'ValidationResult':
        """Create a failed validation result with multiple errors"""
        return ValidationResult(
            is_valid=False,
            errors=errors,
            details=details or {}
        )


class ValidationService:
    """
    Centralized validation service for all input validation.

    Provides consistent validation across API routes and services.
    Uses Pydantic models for type safety and validation rules.

    Example:
        service = ValidationService()

        # Validate agent configuration
        result = service.validate_agent_config({
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INTERN"
        })

        if not result.is_valid:
            raise api_error(
                ErrorCode.VALIDATION_ERROR,
                "Invalid agent configuration",
                details={"errors": result.errors}
            )
    """

    def validate_agent_config(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate agent configuration.

        Args:
            config: Agent configuration dictionary

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        # Required fields
        if "name" not in config:
            errors.append("Agent name is required")
        elif not config["name"] or len(config["name"].strip()) == 0:
            errors.append("Agent name cannot be empty")

        if "domain" not in config:
            errors.append("Domain is required")
        elif config.get("domain") not in [
            "customer_support",
            "data_analysis",
            "content_creation",
            "automation",
            "research"
        ]:
            errors.append(f"Invalid domain: {config.get('domain')}")

        if "maturity_level" in config:
            valid_maturity = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
            if config["maturity_level"] not in valid_maturity:
                errors.append(f"Invalid maturity level: {config['maturity_level']}")

        # Optional fields with validation
        if "temperature" in config:
            temp = config.get("temperature")
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                errors.append("Temperature must be between 0 and 2")

        if "max_tokens" in config:
            tokens = config.get("max_tokens")
            if not isinstance(tokens, int) or tokens < 1 or tokens > 32000:
                errors.append("Max tokens must be between 1 and 32000")

        if errors:
            return ValidationResult.multiple(errors, {"config": config})

        return ValidationResult.success()

    def validate_canvas_data(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate canvas presentation data.

        Args:
            data: Canvas data dictionary

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        # Check required fields
        if "canvas_type" not in data:
            errors.append("canvas_type is required")

        if "component_type" not in data:
            errors.append("component_type is required")

        # Validate canvas_type
        if "canvas_type" in data:
            valid_types = [
                "generic", "docs", "email", "sheets", "orchestration",
                "terminal", "coding", "status_panel", "form"
            ]
            if data["canvas_type"] not in valid_types:
                errors.append(f"Invalid canvas_type: {data['canvas_type']}")

        # Validate component_type based on canvas_type
        if data.get("canvas_type") == "generic":
            valid_components = ["chart", "markdown", "form", "table", "image", "text"]
            if "component_type" in data and data["component_type"] not in valid_components:
                errors.append(f"Invalid component_type for generic canvas: {data.get('component_type')}")

        # Validate chart-specific fields
        if data.get("component_type") == "chart":
            if "chart_type" not in data:
                errors.append("chart_type is required for chart component")
            elif data.get("chart_type") not in ["line", "bar", "pie", "scatter"]:
                errors.append(f"Invalid chart_type: {data.get('chart_type')}")

        if errors:
            return ValidationResult.multiple(errors, {"canvas_data": data})

        return ValidationResult.success()

    def validate_browser_action(self, action: str, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate browser automation action parameters.

        Args:
            action: Action name (navigate, click, fill_form, etc.)
            params: Action parameters

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        if action == "navigate":
            if "url" not in params:
                errors.append("URL is required for navigate action")
            elif not params["url"].startswith(("http://", "https://")):
                errors.append("URL must start with http:// or https://")

        elif action == "click":
            if "selector" not in params:
                errors.append("Selector is required for click action")

        elif action == "fill_form":
            if "selectors" not in params:
                errors.append("Selectors dictionary is required for fill_form")
            elif not isinstance(params["selectors"], dict):
                errors.append("Selectors must be a dictionary")

        elif action == "screenshot":
            if "session_id" not in params:
                errors.append("session_id is required for screenshot action")

        elif action == "execute_script":
            if "script" not in params:
                errors.append("Script is required for execute_script action")
            elif not params["script"].strip():
                errors.append("Script cannot be empty")

        if errors:
            return ValidationResult.multiple(errors, {"action": action, "params": params})

        return ValidationResult.success()

    def validate_device_action(self, action: str, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate device capability action parameters.

        Args:
            action: Action name (camera_snap, screen_record, etc.)
            params: Action parameters

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        if action == "camera_snap":
            if "device_node_id" not in params:
                errors.append("device_node_id is required for camera action")

        elif action == "screen_record_start":
            if "device_node_id" not in params:
                errors.append("device_node_id is required for screen recording")
            if "duration_seconds" in params:
                duration = params.get("duration_seconds")
                if not isinstance(duration, int) or duration < 1 or duration > 3600:
                    errors.append("Duration must be between 1 and 3600 seconds")

        elif action == "get_location":
            if "device_node_id" not in params:
                errors.append("device_node_id is required for location action")

        elif action == "send_notification":
            if "device_node_id" not in params:
                errors.append("device_node_id is required for notification")
            if "message" not in params:
                errors.append("Message is required for notification")

        elif action == "execute_command":
            if "device_node_id" not in params:
                errors.append("device_node_id is required for command execution")
            if "command" not in params:
                errors.append("Command is required for execution")
            # Security: Basic command validation
            if "command" in params:
                cmd = params["command"]
                if len(cmd) > 1000:
                    errors.append("Command too long (max 1000 characters)")
                # Check for potentially dangerous commands
                dangerous = ["rm -rf", "format", "del ", "mkfs", "dd if="]
                if any(dangerous in cmd.lower() for dangerous in dangerous):
                    errors.append("Potentially dangerous command detected")

        if errors:
            return ValidationResult.multiple(errors, {"action": action, "params": params})

        return ValidationResult.success()

    def validate_execution_request(self, request: Dict[str, Any]) -> ValidationResult:
        """
        Validate agent execution request.

        Args:
            request: Execution request dictionary

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        # Required fields
        if "agent_id" not in request:
            errors.append("agent_id is required")

        if "message" not in request:
            errors.append("message is required")

        # Validate message length
        if "message" in request:
            message = request["message"]
            if not isinstance(message, str):
                errors.append("Message must be a string")
            elif len(message.strip()) == 0:
                errors.append("Message cannot be empty")
            elif len(message) > 100000:
                errors.append("Message too long (max 100,000 characters)")

        # Validate session_id if provided
        if "session_id" in request:
            session_id = request["session_id"]
            if not isinstance(session_id, str) or len(session_id) == 0:
                errors.append("session_id must be a non-empty string")

        # Validate streaming parameters if provided
        if "stream" in request and request["stream"]:
            if "max_tokens" in request:
                tokens = request["max_tokens"]
                if not isinstance(tokens, int) or tokens < 1:
                    errors.append("max_tokens must be a positive integer")

        if errors:
            return ValidationResult.multiple(errors, {"request": request})

        return ValidationResult.success()

    def validate_bulk_operation(self, operation: str, items: List[Any]) -> ValidationResult:
        """
        Validate bulk operation parameters.

        Args:
            operation: Operation type (insert, update, delete)
            items: List of items to process

        Returns:
            ValidationResult with validation outcome
        """
        errors = []

        if operation not in ["insert", "update", "delete"]:
            errors.append(f"Invalid operation: {operation}")

        if not isinstance(items, list):
            errors.append("Items must be a list")
        elif len(items) == 0:
            errors.append("Items list cannot be empty")
        elif len(items) > 1000:
            errors.append("Cannot process more than 1000 items at once")

        # Validate each item based on operation type
        if operation == "insert":
            for i, item in enumerate(items[:5]):  # Check first 5 as sample
                if not isinstance(item, dict):
                    errors.append(f"Item {i} must be a dictionary, not {type(item).__name__}")
                elif "id" not in item and "name" not in item:
                    errors.append(f"Item {i} must have 'id' or 'name' field")

        if errors:
            return ValidationResult.multiple(errors, {"operation": operation, "item_count": len(items)})

        return ValidationResult.success()


class AgentConfigModel(BaseModel):
    """
    Pydantic model for agent configuration validation.

    Provides type-safe validation with automatic error messages.
    """

    name: str
    domain: str
    maturity_level: str = "INTERN"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Agent name cannot be empty")
        return v

    @field_validator('domain')
    @classmethod
    def domain_must_be_valid(cls, v):
        valid_domains = ["customer_support", "data_analysis", "content_creation", "automation", "research"]
        if v not in valid_domains:
            raise ValueError(f"Invalid domain: {v}")
        return v

    @field_validator('maturity_level')
    @classmethod
    def maturity_must_be_valid(cls, v):
        valid_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        if v not in valid_levels:
            raise ValueError(f"Invalid maturity level: {v}")
        return v

    @field_validator('temperature')
    @classmethod
    def temperature_must_be_valid(cls, v):
        if v is not None and (v < 0 or v > 2):
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator('max_tokens')
    @classmethod
    def max_tokens_must_be_positive(cls, v):
        if v is not None and (v < 1 or v > 32000):
            raise ValueError("Max tokens must be between 1 and 32000")
        return v


class CanvasDataModel(BaseModel):
    """
    Pydantic model for canvas data validation.
    """

    canvas_type: str
    component_type: str
    title: Optional[str] = None
    content: Optional[str] = None
    chart_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @field_validator('canvas_type')
    @classmethod
    def canvas_type_must_be_valid(cls, v):
        valid_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding", "status_panel", "form"]
        if v not in valid_types:
            raise ValueError(f"Invalid canvas_type: {v}")
        return v

    @field_validator('component_type')
    @classmethod
    def component_type_must_match_canvas_type(cls, v, info):
        canvas_type = info.data.get('canvas_type')
        if canvas_type == "generic":
            valid_components = ["chart", "markdown", "form", "table", "image", "text"]
            if v not in valid_components:
                raise ValueError(f"Invalid component_type for generic canvas: {v}")
        return v


class ExecutionRequestModel(BaseModel):
    """
    Pydantic model for execution request validation.
    """

    agent_id: str
    message: str
    session_id: Optional[str] = None
    stream: bool = False
    max_tokens: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('agent_id')
    @classmethod
    def agent_id_must_not_be_empty(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Agent ID cannot be empty")
        return v

    @field_validator('message')
    @classmethod
    def message_must_not_be_empty(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Message cannot be empty")
        if len(v) > 100000:
            raise ValueError("Message too long (max 100,000 characters)")
        return v

    @field_validator('max_tokens')
    @classmethod
    def max_tokens_must_be_positive(cls, v):
        if v is not None and v < 1:
            raise ValueError("Max tokens must be positive")
        return v
