"""
Standardized Response Models for Atom Platform

Provides consistent Pydantic models for API responses.
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field


# Generic type variable for data field
T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response model.

    Use this for consistent success responses across all endpoints.

    Examples:
        # Return data
        return SuccessResponse[data_type](
            data=agent_dict,
            message="Agent created successfully"
        )

        # Simple success
        return SuccessResponse[None](
            data=None,
            message="Operation completed"
        )
    """

    success: bool = Field(True, description="Always true for success responses")
    data: T = Field(..., description="Response data")
    message: Optional[str] = Field(None, description="Optional success message")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "message": "Operation successful",
                "timestamp": "2026-02-02T12:00:00.000000"
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response model.

    Use this for list endpoints that support pagination.

    Examples:
        # Return paginated list
        return PaginatedResponse[AgentType](
            data=agents,
            total=total_count,
            page=page,
            page_size=page_size
        )
    """

    success: bool = Field(True, description="Always true for success responses")
    data: List[T] = Field(..., description="List of items for current page")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                "pagination": {
                    "total": 100,
                    "page": 1,
                    "page_size": 50,
                    "total_pages": 2,
                    "has_next": True,
                    "has_prev": False
                },
                "timestamp": "2026-02-02T12:00:00.000000"
            }
        }


class ErrorResponse(BaseModel):
    """
    Standard error response model.

    This should be used consistently across all error responses.

    Examples:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error_code="NOT_FOUND",
                message="Agent not found",
                details={"agent_id": "123"}
            ).dict()
        )
    """

    success: bool = Field(False, description="Always false for error responses")
    error_code: str = Field(..., description="Standardized error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request_id: Optional[str] = Field(None, description="Request ID for tracing")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "RESOURCE_NOT_FOUND",
                "message": "Agent with ID '123' not found",
                "details": {"resource_type": "Agent", "resource_id": "123"},
                "timestamp": "2026-02-02T12:00:00.000000",
                "request_id": "req_abc123"
            }
        }


class ValidationErrorResponse(BaseModel):
    """
    Validation error response with field-level errors.

    Use this for validation errors with multiple field issues.

    Examples:
        return ValidationErrorResponse(
            message="Validation failed",
            errors=[
                {"field": "name", "message": "Name is required"},
                {"field": "email", "message": "Invalid email format"}
            ]
        )
    """

    success: bool = Field(False, description="Always false for validation errors")
    error_code: str = Field("VALIDATION_ERROR", description="Error code for validation failures")
    message: str = Field(..., description="Overall validation error message")
    errors: List[Dict[str, Any]] = Field(..., description="List of field-specific validation errors")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "errors": [
                    {"field": "name", "message": "Name is required"},
                    {"field": "email", "message": "Invalid email format"}
                ],
                "timestamp": "2026-02-02T12:00:00.000000"
            }
        }


class BatchOperationResponse(BaseModel):
    """
    Response model for batch operations.

    Use this for bulk create/update/delete operations.

    Examples:
        return BatchOperationResponse(
            success_count=95,
            failure_count=5,
            errors=[{"id": "item1", "error": "Invalid data"}]
        )
    """

    success: bool = Field(True, description="True if any operations succeeded")
    total_count: int = Field(..., description="Total number of operations")
    success_count: int = Field(..., description="Number of successful operations")
    failure_count: int = Field(..., description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="List of errors")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_count": 100,
                "success_count": 95,
                "failure_count": 5,
                "errors": [
                    {"id": "item1", "error": "Invalid data"},
                    {"id": "item2", "error": "Permission denied"}
                ],
                "timestamp": "2026-02-02T12:00:00.000000"
            }
        }


class HealthCheckResponse(BaseModel):
    """
    Health check response model.

    Use this for health check endpoints.

    Examples:
        return HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            checks={"database": "ok", "redis": "ok"}
        )
    """

    status: str = Field(..., description="Overall health status: healthy, degraded, or unhealthy")
    version: str = Field(..., description="Application version")
    checks: Dict[str, str] = Field(default_factory=dict, description="Individual health checks")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "checks": {
                    "database": "ok",
                    "redis": "ok",
                    "api": "ok"
                },
                "timestamp": "2026-02-02T12:00:00.000000"
            }
        }


# Helper functions for creating responses


def create_success_response(
    data: Any,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response dictionary.

    Args:
        data: Response data
        message: Optional success message

    Returns:
        Dictionary with success response format

    Examples:
        return create_success_response(
            {"agent_id": "123"},
            "Agent created successfully"
        )
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }


def create_paginated_response(
    data: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """
    Create a standardized paginated response dictionary.

    Args:
        data: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page

    Returns:
        Dictionary with pagination metadata

    Examples:
        return create_paginated_response(
            agents,
            total_count,
            page=1,
            page_size=50
        )
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "success": True,
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.

    Args:
        error_code: Standardized error code
        message: Human-readable error message
        details: Additional error details
        request_id: Request ID for tracing

    Returns:
        Dictionary with error response format

    Examples:
        return create_error_response(
            "NOT_FOUND",
            "Agent not found",
            {"agent_id": "123"}
        )
    """
    response = {
        "success": False,
        "error_code": error_code,
        "message": message,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }

    if request_id:
        response["request_id"] = request_id

    return response
