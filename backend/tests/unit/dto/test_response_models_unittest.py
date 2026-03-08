#!/usr/bin/env python3
"""
Simple test runner for DTO tests without pytest
"""
import sys
import os

# Add backend to path
backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, backend_path)

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

def test_success_response_with_data():
    """Test SuccessResponse with dict data"""
    response = SuccessResponse[Dict[str, Any]](
        data={"id": "123", "name": "Test Agent"},
        message="Agent created successfully"
    )
    assert response.success is True
    assert response.data == {"id": "123", "name": "Test Agent"}
    assert response.message == "Agent created successfully"
    assert response.timestamp is not None
    print("✓ test_success_response_with_data")

def test_success_response_with_none_data():
    """Test SuccessResponse with None data field"""
    response = SuccessResponse[None](
        data=None,
        message="Operation completed"
    )
    assert response.success is True
    assert response.data is None
    assert response.message == "Operation completed"
    print("✓ test_success_response_with_none_data")

def test_success_response_serialization():
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
    print("✓ test_success_response_serialization")

def test_success_response_generic_specialization_str():
    """Test SuccessResponse with str type parameter"""
    response = SuccessResponse[str](
        data="Simple string data",
        message="Text response"
    )
    assert response.data == "Simple string data"
    assert isinstance(response.data, str)
    print("✓ test_success_response_generic_specialization_str")

def test_success_response_generic_specialization_list():
    """Test SuccessResponse with list type parameter"""
    response = SuccessResponse[List[int]](
        data=[1, 2, 3, 4, 5],
        message="List response"
    )
    assert response.data == [1, 2, 3, 4, 5]
    assert isinstance(response.data, list)
    print("✓ test_success_response_generic_specialization_list")

def test_success_response_timestamp_auto_generated():
    """Test timestamp field is auto-populated"""
    response1 = SuccessResponse[str](data="test")
    response2 = SuccessResponse[str](data="test")
    assert response1.timestamp is not None
    assert response2.timestamp is not None
    # Verify ISO format
    datetime.fromisoformat(response1.timestamp.replace('Z', '+00:00'))
    datetime.fromisoformat(response2.timestamp.replace('Z', '+00:00'))
    print("✓ test_success_response_timestamp_auto_generated")

def test_paginated_response_structure():
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
    print("✓ test_paginated_response_structure")

def test_paginated_response_accepts_any_dict_metadata():
    """Test that pagination field accepts any dict (Pydantic doesn't validate nested dict keys)"""
    # Pydantic v2 accepts any dict for Dict[str, Any] fields without validating inner structure
    response = PaginatedResponse[Dict[str, str]](
        data=[{"id": "1"}],
        pagination={"page": 1, "page_size": 50}  # missing 'total' but still valid
    )
    assert response.success is True
    assert response.pagination == {"page": 1, "page_size": 50}
    print("✓ test_paginated_response_accepts_any_dict_metadata")

def test_paginated_response_empty_data():
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
    print("✓ test_paginated_response_empty_data")

def test_error_response_structure():
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
    print("✓ test_error_response_structure")

def test_error_response_with_minimal_fields():
    """Test only required fields (details is optional)"""
    response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Invalid input data"
    )
    assert response.success is False
    assert response.error_code == "VALIDATION_ERROR"
    assert response.message == "Invalid input data"
    assert response.details is None
    print("✓ test_error_response_with_minimal_fields")

def test_error_response_serialization():
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
    print("✓ test_error_response_serialization")

def test_create_success_response():
    """Test create_success_response helper function"""
    result = create_success_response(
        data={"agent_id": "123"},
        message="Agent created successfully"
    )
    assert result["success"] is True
    assert result["data"] == {"agent_id": "123"}
    assert result["message"] == "Agent created successfully"
    assert "timestamp" in result
    print("✓ test_create_success_response")

def test_create_paginated_response():
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
    print("✓ test_create_paginated_response")

def test_create_error_response():
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
    print("✓ test_create_error_response")

if __name__ == "__main__":
    # Run all tests
    tests = [
        test_success_response_with_data,
        test_success_response_with_none_data,
        test_success_response_serialization,
        test_success_response_generic_specialization_str,
        test_success_response_generic_specialization_list,
        test_success_response_timestamp_auto_generated,
        test_paginated_response_structure,
        test_paginated_response_accepts_any_dict_metadata,
        test_paginated_response_empty_data,
        test_error_response_structure,
        test_error_response_with_minimal_fields,
        test_error_response_serialization,
        test_create_success_response,
        test_create_paginated_response,
        test_create_error_response,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed.append(test.__name__)

    print(f"\n{'='*60}")
    print(f"Tests run: {len(tests)}")
    print(f"Passed: {len(tests) - len(failed)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print(f"\nFailed tests: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)
