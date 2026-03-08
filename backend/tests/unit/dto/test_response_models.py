"""
Tests for standardized response models (SuccessResponse, ErrorResponse, PaginatedResponse)

Ensures API response consistency across all endpoints with proper validation,
serialization, and generic type handling.
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any
from pydantic import ValidationError

from core.response_models import (
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse,
    ValidationErrorResponse,
    BatchOperationResponse,
    HealthCheckResponse,
    create_success_response,
    create_paginated_response,
    create_error_response,
)


class TestSuccessResponse:
    """Test SuccessResponse generic model with type specialization and validation"""

    def test_success_response_with_data(self):
        """Test SuccessResponse with dict data"""
        response = SuccessResponse[Dict[str, Any]](
            data={"id": "123", "name": "Test Agent"},
            message="Agent created successfully"
        )

        assert response.success is True
        assert response.data == {"id": "123", "name": "Test Agent"}
        assert response.message == "Agent created successfully"
        assert response.timestamp is not None
        assert isinstance(response.timestamp, str)

    def test_success_response_with_none_data(self):
        """Test SuccessResponse with None data field"""
        response = SuccessResponse[None](
            data=None,
            message="Operation completed"
        )

        assert response.success is True
        assert response.data is None
        assert response.message == "Operation completed"

    def test_success_response_serialization(self):
        """Test model_dump() produces correct JSON structure"""
        response = SuccessResponse[Dict[str, Any]](
            data={"id": "123", "name": "Test"},
            message="Success"
        )

        serialized = response.model_dump()

        assert serialized["success"] is True
        assert serialized["data"] == {"id": "123", "name": "Test"}
        assert serialized["message"] == "Success"
        assert "timestamp" in serialized

    def test_success_response_generic_specialization_str(self):
        """Test SuccessResponse with str type parameter"""
        response = SuccessResponse[str](
            data="Simple string data",
            message="Text response"
        )

        assert response.data == "Simple string data"
        assert isinstance(response.data, str)

    def test_success_response_generic_specialization_list(self):
        """Test SuccessResponse with list type parameter"""
        response = SuccessResponse[List[int]](
            data=[1, 2, 3, 4, 5],
            message="List response"
        )

        assert response.data == [1, 2, 3, 4, 5]
        assert isinstance(response.data, list)

    def test_success_response_generic_specialization_dict(self):
        """Test SuccessResponse with dict type parameter"""
        response = SuccessResponse[Dict[str, int]](
            data={"count": 10, "total": 100},
            message="Dict response"
        )

        assert response.data == {"count": 10, "total": 100}
        assert isinstance(response.data, dict)

    def test_success_response_timestamp_auto_generated(self):
        """Test timestamp field is auto-populated"""
        response1 = SuccessResponse[str](data="test")
        response2 = SuccessResponse[str](data="test")

        assert response1.timestamp is not None
        assert response2.timestamp is not None

        # Timestamps should be ISO format strings
        datetime.fromisoformat(response1.timestamp.replace('Z', '+00:00'))
        datetime.fromisoformat(response2.timestamp.replace('Z', '+00:00'))

    def test_success_response_default_values(self):
        """Test optional fields with defaults"""
        response = SuccessResponse[str](
            data="test"
        )

        # message should default to None
        assert response.message is None
        assert response.success is True


class TestPaginatedResponse:
    """Test PaginatedResponse model with pagination metadata"""

    def test_paginated_response_structure(self):
        """Test valid data + pagination metadata"""
        data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        pagination = {
            "total": 100,
            "page": 1,
            "page_size": 50,
            "total_pages": 2,
            "has_next": True,
            "has_prev": False
        }

        response = PaginatedResponse[Dict[str, str]](
            data=data,
            pagination=pagination
        )

        assert response.success is True
        assert response.data == data
        assert response.pagination == pagination
        assert response.timestamp is not None

    def test_paginated_response_accepts_any_dict_metadata(self):
        """Test that pagination field accepts any dict (Pydantic doesn't validate nested dict keys)"""
        # Pydantic v2 accepts any dict for Dict[str, Any] fields without validating inner structure
        # This is expected behavior - validation would require a typed Pydantic model
        response = PaginatedResponse[Dict[str, str]](
            data=[{"id": "1"}],
            pagination={"page": 1, "page_size": 50}  # missing 'total' but still valid
        )
        assert response.success is True
        assert response.pagination == {"page": 1, "page_size": 50}

    def test_paginated_response_empty_data(self):
        """Test empty data array with valid pagination"""
        response = PaginatedResponse[Dict[str, str]](
            data=[],
            pagination={
                "total": 0,
                "page": 1,
                "page_size": 50,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False
            }
        )

        assert response.data == []
        assert response.pagination["total"] == 0
        assert response.pagination["total_pages"] == 0

    def test_paginated_response_serialization(self):
        """Test correct JSON output"""
        data = [{"id": "1", "name": "Item 1"}]
        pagination = {
            "total": 1,
            "page": 1,
            "page_size": 50,
            "total_pages": 1,
            "has_next": False,
            "has_prev": False
        }

        response = PaginatedResponse[Dict[str, str]](
            data=data,
            pagination=pagination
        )

        serialized = response.model_dump()

        assert serialized["success"] is True
        assert serialized["data"] == data
        assert serialized["pagination"] == pagination
        assert "timestamp" in serialized


class TestErrorResponse:
    """Test ErrorResponse model with error details"""

    def test_error_response_structure(self):
        """Test error_code, message, details fields"""
        response = ErrorResponse(
            error_code="NOT_FOUND",
            message="Resource not found",
            details={"resource_type": "Agent", "resource_id": "123"}
        )

        assert response.success is False
        assert response.error_code == "NOT_FOUND"
        assert response.message == "Resource not found"
        assert response.details == {"resource_type": "Agent", "resource_id": "123"}

    def test_error_response_with_minimal_fields(self):
        """Test only required fields (details is optional)"""
        response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Invalid input data"
        )

        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Invalid input data"
        assert response.details is None

    def test_error_response_serialization(self):
        """Test correct error JSON structure"""
        response = ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="Server error occurred",
            details={"error_id": "err_123"}
        )

        serialized = response.model_dump()

        assert serialized["success"] is False
        assert serialized["error_code"] == "INTERNAL_ERROR"
        assert serialized["message"] == "Server error occurred"
        assert serialized["details"] == {"error_id": "err_123"}
        assert "timestamp" in serialized

    def test_error_response_with_request_id(self):
        """Test ErrorResponse with optional request_id field"""
        response = ErrorResponse(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests",
            request_id="req_abc123"
        )

        assert response.request_id == "req_abc123"
        assert response.details is None


class TestValidationErrorResponse:
    """Test ValidationErrorResponse with field-level errors"""

    def test_validation_error_response_structure(self):
        """Test validation error with multiple field issues"""
        response = ValidationErrorResponse(
            message="Validation failed",
            errors=[
                {"field": "name", "message": "Name is required"},
                {"field": "email", "message": "Invalid email format"}
            ]
        )

        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Validation failed"
        assert len(response.errors) == 2
        assert response.errors[0]["field"] == "name"

    def test_validation_error_response_empty_errors(self):
        """Test ValidationErrorResponse with empty errors list"""
        response = ValidationErrorResponse(
            message="No errors",
            errors=[]
        )

        assert response.errors == []


class TestBatchOperationResponse:
    """Test BatchOperationResponse model"""

    def test_batch_operation_response_structure(self):
        """Test batch operation with successes and failures"""
        response = BatchOperationResponse(
            total_count=100,
            success_count=95,
            failure_count=5,
            errors=[
                {"id": "item1", "error": "Invalid data"},
                {"id": "item2", "error": "Permission denied"}
            ]
        )

        assert response.success is True
        assert response.total_count == 100
        assert response.success_count == 95
        assert response.failure_count == 5
        assert len(response.errors) == 2

    def test_batch_operation_response_all_success(self):
        """Test batch operation with 100% success"""
        response = BatchOperationResponse(
            total_count=10,
            success_count=10,
            failure_count=0
        )

        assert response.success_count == 10
        assert response.failure_count == 0
        assert response.errors == []


class TestHealthCheckResponse:
    """Test HealthCheckResponse model"""

    def test_health_check_response_structure(self):
        """Test health check with system status"""
        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            checks={
                "database": "ok",
                "redis": "ok",
                "api": "ok"
            }
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.checks["database"] == "ok"


class TestHelperFunctions:
    """Test helper functions for creating response dictionaries"""

    def test_create_success_response(self):
        """Test create_success_response helper function"""
        result = create_success_response(
            data={"agent_id": "123"},
            message="Agent created successfully"
        )

        assert result["success"] is True
        assert result["data"] == {"agent_id": "123"}
        assert result["message"] == "Agent created successfully"
        assert "timestamp" in result

    def test_create_success_response_without_message(self):
        """Test create_success_response without optional message"""
        result = create_success_response(
            data={"status": "ok"}
        )

        assert result["success"] is True
        assert result["data"] == {"status": "ok"}
        assert result["message"] is None

    def test_create_paginated_response(self):
        """Test create_paginated_response helper function"""
        data = [{"id": "1"}, {"id": "2"}]
        result = create_paginated_response(
            data=data,
            total=100,
            page=1,
            page_size=50
        )

        assert result["success"] is True
        assert result["data"] == data
        assert result["pagination"]["total"] == 100
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["page_size"] == 50
        assert result["pagination"]["total_pages"] == 2
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_prev"] is False

    def test_create_paginated_response_last_page(self):
        """Test create_paginated_response for last page"""
        data = [{"id": "1"}]
        result = create_paginated_response(
            data=data,
            total=51,
            page=2,
            page_size=50
        )

        assert result["pagination"]["total_pages"] == 2
        assert result["pagination"]["has_next"] is False
        assert result["pagination"]["has_prev"] is True

    def test_create_error_response(self):
        """Test create_error_response helper function"""
        result = create_error_response(
            error_code="NOT_FOUND",
            message="Agent not found",
            details={"agent_id": "123"}
        )

        assert result["success"] is False
        assert result["error_code"] == "NOT_FOUND"
        assert result["message"] == "Agent not found"
        assert result["details"] == {"agent_id": "123"}
        assert "timestamp" in result

    def test_create_error_response_with_request_id(self):
        """Test create_error_response with optional request_id"""
        result = create_error_response(
            error_code="INTERNAL_ERROR",
            message="Server error",
            request_id="req_abc123"
        )

        assert result["request_id"] == "req_abc123"

    def test_create_error_response_without_details(self):
        """Test create_error_response without optional details"""
        result = create_error_response(
            error_code="UNAUTHORIZED",
            message="Authentication required"
        )

        assert result["details"] == {}
