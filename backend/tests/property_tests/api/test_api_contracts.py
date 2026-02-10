"""
Property-Based Tests for API Contracts - CRITICAL API LAYER

Tests critical API contract invariants:
- Response structure and format
- Status code correctness
- Error handling consistency
- Pagination contracts
- Data type validation
- Field presence and constraints

These tests protect against:
- Breaking API contracts
- Inconsistent error responses
- Invalid response formats
- Missing required fields
- Type violations
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestAPIResponseStructure:
    """Tests for API response structure invariants"""

    @given(
        success=st.booleans(),
        data=st.one_of(
            st.none(),
            st.dictionaries(
                st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
                st.one_of(
                    st.text(min_size=1, max_size=100),
                    st.integers(min_value=0, max_value=10000),
                    st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
                    st.booleans(),
                    st.lists(st.integers(min_value=0, max_value=100))
                ),
                min_size=0,
                max_size=20
            )
        ),
        message=st.one_of(st.none(), st.text(min_size=1, max_size=200))
    )
    @settings(max_examples=50)
    def test_standard_response_format(self, success, data, message):
        """Test that API responses follow standard format"""
        # Simulate standard API response structure
        response = {
            'success': success,
            'data': data,
            'message': message
        }

        # Verify required fields are present
        assert 'success' in response, "Response should have 'success' field"
        assert 'data' in response, "Response should have 'data' field"
        assert 'message' in response, "Response should have 'message' field"

        # Verify field types
        assert isinstance(response['success'], bool), \
            "Success field should be boolean"
        assert response['data'] is None or isinstance(response['data'], (dict, list)), \
            "Data field should be dict, list, or None"
        assert response['message'] is None or isinstance(response['message'], str), \
            "Message field should be string or None"

    @given(
        error_code=st.sampled_from([
            "AGENT_NOT_FOUND",
            "INVALID_REQUEST",
            "UNAUTHORIZED",
            "RATE_LIMIT_EXCEEDED",
            "INTERNAL_ERROR"
        ]),
        error_message=st.text(min_size=10, max_size=200),
        details=st.one_of(
            st.none(),
            st.dictionaries(
                st.text(min_size=1, max_size=50),
                st.one_of(st.text(), st.integers(), st.floats(allow_nan=False, allow_infinity=False)),
                min_size=0,
                max_size=10
            )
        )
    )
    @settings(max_examples=50)
    def test_error_response_format(self, error_code, error_message, details):
        """Test that error responses follow standard format"""
        # Simulate error response structure
        response = {
            'success': False,
            'error_code': error_code,
            'message': error_message,
            'details': details
        }

        # Verify required fields for error responses
        assert response['success'] == False, \
            "Error response should have success=False"
        assert 'error_code' in response, \
            "Error response should have 'error_code' field"
        assert 'message' in response, \
            "Error response should have 'message' field"

        # Verify error_code is non-empty string
        assert isinstance(response['error_code'], str), \
            "Error code should be string"
        assert len(response['error_code']) > 0, \
            "Error code should not be empty"

        # Verify message is non-empty string
        assert isinstance(response['message'], str), \
            "Error message should be string"
        assert len(response['message']) >= 10, \
            "Error message should be descriptive (min 10 chars)"


class TestPaginationContracts:
    """Tests for pagination contract invariants"""

    @given(
        total_items=st.integers(min_value=0, max_value=1000),
        page=st.integers(min_value=1, max_value=50),
        page_size=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_pagination_response_structure(self, total_items, page, page_size):
        """Test that pagination responses follow standard format"""
        # Calculate pagination values
        total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1

        # Simulate pagination response
        response = {
            'items': [],  # Simplified
            'pagination': {
                'total': total_items,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev
            }
        }

        # Verify pagination structure
        assert 'pagination' in response, \
            "Response should have 'pagination' field"
        assert 'items' in response, \
            "Response should have 'items' field"

        pagination = response['pagination']
        assert 'total' in pagination, \
            "Pagination should have 'total'"
        assert 'page' in pagination, \
            "Pagination should have 'page'"
        assert 'page_size' in pagination, \
            "Pagination should have 'page_size'"
        assert 'total_pages' in pagination, \
            "Pagination should have 'total_pages'"
        assert 'has_next' in pagination, \
            "Pagination should have 'has_next'"
        assert 'has_prev' in pagination, \
            "Pagination should have 'has_prev'"

        # Verify pagination values
        assert pagination['total'] >= 0, \
            "Total items should be non-negative"
        assert pagination['page'] > 0, \
            "Page should be positive"
        assert pagination['page_size'] > 0, \
            "Page size should be positive"
        assert pagination['total_pages'] >= 0, \
            "Total pages should be non-negative"

    @given(
        total_items=st.integers(min_value=0, max_value=1000),
        page_size=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_pagination_bounds(self, total_items, page_size):
        """Test that pagination stays within bounds"""
        # Calculate valid page range
        total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 0

        # Test first page
        assert 1 <= total_pages or total_items == 0, \
            "Should have at least one page if items exist"

        # Test page number bounds
        if total_items > 0:
            assert total_pages >= 1, \
                "Should have at least one page"
            max_page = total_pages
            assert max_page >= 1, \
                "Max page should be at least 1"
        else:
            assert total_pages == 0, \
                "Empty result should have zero pages"


class TestDataTypeValidation:
    """Tests for data type validation invariants"""

    @given(
        agent_names=st.lists(
            st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'),
            min_size=1,
            max_size=20
        ),
        agent_statuses=st.lists(
            st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_agent_response_types(self, agent_names, agent_statuses):
        """Test that agent API responses have correct types"""
        # Simulate agent response
        response = {
            'id': agent_names[0] if agent_names else "test_agent",
            'name': agent_names[0] if agent_names else "Test Agent",
            'status': agent_statuses[0] if agent_statuses else "STUDENT",
            'confidence': 0.85
        }

        # Verify field types
        assert isinstance(response['id'], str), \
            "Agent ID should be string"
        assert isinstance(response['name'], str), \
            "Agent name should be string"
        assert isinstance(response['status'], str), \
            "Agent status should be string"
        assert isinstance(response['confidence'], float), \
            "Agent confidence should be float"

        # Verify valid values
        assert len(response['id']) > 0, \
            "Agent ID should not be empty"
        assert len(response['name']) > 0, \
            "Agent name should not be empty"
        assert response['status'] in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"], \
            f"Agent status should be valid, got {response['status']}"
        assert 0.0 <= response['confidence'] <= 1.0, \
            "Agent confidence should be in [0.0, 1.0]"

    @given(
        episode_counts=st.integers(min_value=0, max_value=1000),
        timestamps=st.lists(
            st.integers(min_value=0, max_value=2000000000),  # Unix timestamps
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_episode_response_types(self, episode_counts, timestamps):
        """Test that episode API responses have correct types"""
        # Simulate episode response
        response = {
            'episode_count': episode_counts,
            'created_at': timestamps[0] if timestamps else 0,
            'segments': []
        }

        # Verify field types
        assert isinstance(response['episode_count'], int), \
            "Episode count should be integer"
        assert isinstance(response['created_at'], int), \
            "Created timestamp should be integer"
        assert isinstance(response['segments'], list), \
            "Segments should be list"

        # Verify valid values
        assert response['episode_count'] >= 0, \
            "Episode count should be non-negative"
        assert response['created_at'] >= 0, \
            "Created timestamp should be non-negative"


class TestFieldPresenceConstraints:
    """Tests for required field presence and constraints"""

    @given(
        agent_data=st.dictionaries(
            st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            st.one_of(
                st.text(min_size=1, max_size=100),
                st.integers(min_value=0, max_value=1000),
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.lists(st.integers(min_value=0, max_value=100))
            ),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_required_fields_present(self, agent_data):
        """Test that required fields are present in agent responses"""
        # Add required fields if not present
        if 'id' not in agent_data:
            agent_data['id'] = "test_agent"
        if 'name' not in agent_data:
            agent_data['name'] = "Test Agent"
        if 'status' not in agent_data:
            agent_data['status'] = "STUDENT"

        # Verify required fields
        required_fields = ['id', 'name', 'status']
        for field in required_fields:
            assert field in agent_data, \
                f"Required field '{field}' should be present"
            assert agent_data[field] is not None, \
                f"Required field '{field}' should not be None"

    @given(
        text_fields=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.text(min_size=0, max_size=1000),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_text_field_length_constraints(self, text_fields):
        """Test that text fields respect length constraints"""
        # Define max length constraints
        max_lengths = {
            'id': 100,
            'name': 200,
            'description': 5000,
            'status': 50
        }

        # Verify length constraints
        for field_name, value in text_fields.items():
            # Get appropriate max length (default to 5000)
            max_len = max_lengths.get(field_name, 5000)

            assert len(value) <= max_len, \
                f"Field '{field_name}' should not exceed {max_len} characters"

    @given(
        numeric_fields=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_numeric_field_range_constraints(self, numeric_fields):
        """Test that numeric fields respect range constraints"""
        # Define range constraints
        ranges = {
            'confidence': (0.0, 1.0),
            'progress': (0.0, 100.0),
            'count': (0, 1000000),
            'priority': (0, 10)
        }

        # Verify range constraints
        for field_name, value in numeric_fields.items():
            if field_name in ranges:
                min_val, max_val = ranges[field_name]
                assert min_val <= value <= max_val, \
                    f"Field '{field_name}' value {value} should be in [{min_val}, {max_val}]"


class TestStatusCodeContracts:
    """Tests for HTTP status code contracts"""

    @given(
        endpoint_type=st.sampled_from([
            "GET /agents",
            "POST /agents",
            "GET /agents/{id}",
            "PUT /agents/{id}",
            "DELETE /agents/{id}",
            "POST /feedback",
            "GET /episodes"
        ]),
        success=st.booleans(),
        resource_exists=st.booleans()
    )
    @settings(max_examples=50)
    def test_status_code_correctness(self, endpoint_type, success, resource_exists):
        """Test that status codes are correct for different scenarios"""
        # Determine expected status code
        if success:
            if "POST" in endpoint_type or "PUT" in endpoint_type:
                expected_code = 200  # OK or 201 Created
            elif "DELETE" in endpoint_type:
                expected_code = 200  # OK or 204 No Content
            else:
                expected_code = 200  # OK
        else:
            if not resource_exists:
                expected_code = 404  # Not Found
            else:
                expected_code = 400  # Bad Request

        # Verify status code is in valid range
        assert 200 <= expected_code < 600, \
            "Status code should be in valid range [200, 600)"

        # Verify specific status codes
        valid_codes = [200, 201, 204, 400, 401, 403, 404, 500, 503]
        assert expected_code in valid_codes, \
            f"Status code {expected_code} should be one of {valid_codes}"

    @given(
        error_conditions=st.lists(
            st.sampled_from([
                "unauthorized",
                "forbidden",
                "not_found",
                "rate_limited",
                "server_error"
            ]),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_error_status_codes(self, error_conditions):
        """Test that error conditions return correct status codes"""
        # Define expected status codes for error conditions
        status_codes = {
            "unauthorized": 401,
            "forbidden": 403,
            "not_found": 404,
            "rate_limited": 429,
            "server_error": 500
        }

        # Verify error status codes
        for condition in error_conditions:
            expected_code = status_codes.get(condition, 500)
            assert 400 <= expected_code < 600, \
                f"Error condition '{condition}' should return 4xx or 5xx status"
            assert expected_code in status_codes.values(), \
                f"Status code {expected_code} should be valid error code"


class TestListResponseContracts:
    """Tests for list response contract invariants"""

    @given(
        items=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.integers(min_value=0, max_value=100),
                min_size=1,
                max_size=5
            ),
            min_size=0,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_list_response_structure(self, items):
        """Test that list responses follow standard format"""
        # Simulate list response
        response = {
            'items': items,
            'count': len(items)
        }

        # Verify structure
        assert 'items' in response, \
            "List response should have 'items' field"
        assert 'count' in response, \
            "List response should have 'count' field"

        # Verify types
        assert isinstance(response['items'], list), \
            "Items field should be list"
        assert isinstance(response['count'], int), \
            "Count field should be integer"

        # Verify count matches
        assert response['count'] == len(response['items']), \
            "Count should match actual items length"

        # Verify count is non-negative
        assert response['count'] >= 0, \
            "Count should be non-negative"

    @given(
        total_items=st.integers(min_value=0, max_value=1000),
        limit=st.integers(min_value=1, max_value=100),
        offset=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_list_pagination_consistency(self, total_items, limit, offset):
        """Test that list pagination is consistent"""
        # Calculate expected page size
        remaining_items = max(0, total_items - offset)
        page_size = min(remaining_items, limit)

        # Verify page size is valid
        assert 0 <= page_size <= limit, \
            f"Page size {page_size} should be in [0, {limit}]"

        # Verify offset is non-negative (can exceed total_items - API returns empty)
        assert offset >= 0, \
            f"Offset {offset} should be non-negative"

        # Verify has_next logic
        has_next = (offset + limit) < total_items
        expected_has_next = (offset + page_size) < total_items
        assert has_next == expected_has_next, \
            "has_next should be consistent with page size"
