"""
Tests for Response Models

Tests for response model classes including:
- Pydantic model validation
- Field validation
- Model serialization
- Error response models
"""

import pytest
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError


# Mock response models if they don't exist
try:
    from core.response_models import (
        SuccessResponse,
        ErrorResponse,
        PaginatedResponse,
        AgentResponse,
        WorkflowResponse,
        CanvasResponse
    )
except ImportError:
    # Create mock models for testing
    class SuccessResponse(BaseModel):
        success: bool = True
        message: Optional[str] = None
        data: Optional[dict] = None

    class ErrorResponse(BaseModel):
        success: bool = False
        error_code: str
        message: str
        details: Optional[dict] = None

    class PaginatedResponse(BaseModel):
        items: List[dict] = []
        total: int = 0
        page: int = 1
        page_size: int = 10
        has_next: bool = False
        has_prev: bool = False

    class AgentResponse(BaseModel):
        agent_id: str
        name: str
        status: str
        confidence_score: float

    class WorkflowResponse(BaseModel):
        workflow_id: str
        name: str
        status: str
        steps: List[str] = []

    class CanvasResponse(BaseModel):
        canvas_id: str
        type: str
        status: str
        components: List[dict] = []


class TestSuccessResponse:
    """Tests for SuccessResponse model."""

    def test_success_response_creation(self):
        """Test creating success response."""
        response = SuccessResponse(
            success=True,
            message="Operation completed",
            data={"id": "123"}
        )

        assert response.success is True
        assert response.message == "Operation completed"
        assert response.data["id"] == "123"

    def test_success_response_minimal(self):
        """Test creating minimal success response."""
        response = SuccessResponse()

        assert response.success is True
        assert response.message is None
        assert response.data is None


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_creation(self):
        """Test creating error response."""
        response = ErrorResponse(
            success=False,
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "email", "issue": "required"}
        )

        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.details["field"] == "email"

    def test_error_response_validation(self):
        """Test ErrorResponse validates required fields."""
        # Missing error_code and message
        with pytest.raises(ValidationError):
            ErrorResponse(
                success=False
            )

    def test_error_response_serialization(self):
        """Test ErrorResponse JSON serialization."""
        response = ErrorResponse(
            success=False,
            error_code="NOT_FOUND",
            message="Resource not found"
        )

        json_data = response.model_dump()

        assert json_data["success"] is False
        assert json_data["error_code"] == "NOT_FOUND"


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_paginated_response_creation(self):
        """Test creating paginated response."""
        items = [
            {"id": "1", "name": "Item 1"},
            {"id": "2", "name": "Item 2"}
        ]

        response = PaginatedResponse(
            items=items,
            total=2,
            page=1,
            page_size=2,
            has_next=False,
            has_prev=False
        )

        assert len(response.items) == 2
        assert response.total == 2
        assert response.has_next is False
        assert response.has_prev is False

    def test_paginated_response_pagination(self):
        """Test paginated response with pagination."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page=5,
            page_size=20,
            has_next=True,
            has_prev=True
        )

        assert response.page == 5
        assert response.has_next is True
        assert response.has_prev is True


class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_agent_response_creation(self):
        """Test creating agent response."""
        response = AgentResponse(
            agent_id="agent-123",
            name="Test Agent",
            status="ACTIVE",
            confidence_score=0.95
        )

        assert response.agent_id == "agent-123"
        assert response.confidence_score == 0.95

    def test_agent_response_validation(self):
        """Test AgentResponse field validation."""
        # Invalid confidence score
        with pytest.raises(ValidationError):
            AgentResponse(
                agent_id="agent-123",
                name="Test Agent",
                status="ACTIVE",
                confidence_score=1.5  # > 1.0
            )

    def test_agent_response_serialization(self):
        """Test AgentResponse JSON serialization."""
        response = AgentResponse(
            agent_id="agent-123",
            name="Test Agent",
            status="ACTIVE",
            confidence_score=0.95
        )

        json_data = response.model_dump()

        assert json_data["agent_id"] == "agent-123"
        assert json_data["status"] == "ACTIVE"


class TestWorkflowResponse:
    """Tests for WorkflowResponse model."""

    def test_workflow_response_creation(self):
        """Test creating workflow response."""
        response = WorkflowResponse(
            workflow_id="wf-123",
            name="Test Workflow",
            status="RUNNING",
            steps=["step1", "step2", "step3"]
        )

        assert response.workflow_id == "wf-123"
        assert len(response.steps) == 3
        assert response.status == "RUNNING"

    def test_workflow_response_empty_steps(self):
        """Test workflow response with no steps."""
        response = WorkflowResponse(
            workflow_id="wf-456",
            name="Empty Workflow",
            status="PENDING"
        )

        assert len(response.steps) == 0


class TestCanvasResponse:
    """Tests for CanvasResponse model."""

    def test_canvas_response_creation(self):
        """Test creating canvas response."""
        components = [
            {"type": "chart", "id": "comp-1"},
            {"type": "text", "id": "comp-2"}
        ]

        response = CanvasResponse(
            canvas_id="canvas-123",
            type="dashboard",
            status="active",
            components=components
        )

        assert response.canvas_id == "canvas-123"
        assert len(response.components) == 2

    def test_canvas_response_validation(self):
        """Test CanvasResponse field validation."""
        # Invalid status
        with pytest.raises(ValidationError):
            CanvasResponse(
                canvas_id="canvas-123",
                type="dashboard",
                status="invalid_status",
                components=[]
            )


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_serialize_deserialize_success_response(self):
        """Test round-trip serialization of SuccessResponse."""
        original = SuccessResponse(
            success=True,
            message="Test",
            data={"key": "value"}
        )

        # Serialize
        json_data = original.model_dump_json()

        # Deserialize
        restored = SuccessResponse.model_validate_json(json_data)

        assert restored.success == original.success
        assert restored.message == original.message
        assert restored.data == original.data

    def test_serialize_deserialize_error_response(self):
        """Test round-trip serialization of ErrorResponse."""
        original = ErrorResponse(
            success=False,
            error_code="TEST_ERROR",
            message="Test error",
            details={"detail": "info"}
        )

        json_data = original.model_dump_json()
        restored = ErrorResponse.model_validate_json(json_data)

        assert restored.error_code == original.error_code


class TestEdgeCases:
    """Tests for edge cases."""

    def test_response_with_nested_data(self):
        """Test response with nested dictionary data."""
        response = SuccessResponse(
            success=True,
            data={
                "user": {
                    "id": "123",
                    "profile": {"name": "Test"}
                }
            }
        )

        assert response.data["user"]["profile"]["name"] == "Test"

    def test_response_with_list_data(self):
        """Test response with list data."""
        response = SuccessResponse(
            success=True,
            data={
                "items": [1, 2, 3],
                "count": 3
            }
        )

        assert response.data["items"] == [1, 2, 3]

    def test_response_with_datetime(self):
        """Test response with datetime field."""
        if "timestamp" in SuccessResponse.__annotations__:
            response = SuccessResponse(
                success=True,
                timestamp=datetime.utcnow()
            )

            assert response.timestamp is not None
        else:
            # Test adding timestamp to data
            response = SuccessResponse(
                success=True,
                data={"timestamp": datetime.utcnow().isoformat()}
            )

            assert "timestamp" in response.data


class TestValidationErrors:
    """Tests for validation error scenarios."""

    def test_invalid_confidence_score(self):
        """Test validation of confidence_score bounds."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                agent_id="agent-123",
                name="Test",
                status="ACTIVE",
                confidence_score=2.0
            )

        errors = exc_info.value.errors()
        assert any("confidence_score" in str(err) for err in errors)

    def test_missing_required_field(self):
        """Test validation error for missing required field."""
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(
                success=False,
                error_code="ERR_001"
                # Missing message
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0


class TestModelInheritance:
    """Tests for model inheritance and polymorphism."""

    def test_base_response_fields(self):
        """Test that all response models have base fields."""
        success = SuccessResponse(success=True)
        error = ErrorResponse(
            success=False,
            error_code="E001",
            message="Error"
        )

        # Both should have success field
        assert hasattr(success, "success")
        assert hasattr(error, "success")

    def test_response_polymorphism(self):
        """Test treating responses as base model."""
        responses: List[SuccessResponse] = [
            SuccessResponse(success=True, data={"id": "1"}),
            SuccessResponse(success=True, message="Done")
        ]

        for response in responses:
            assert response.success is True
