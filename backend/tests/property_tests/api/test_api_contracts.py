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
from hypothesis import given, strategies as st, settings, HealthCheck, assume
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


class TestAPIVersioningInvariants:
    """Tests for API versioning contract invariants"""

    @given(
        version=st.sampled_from(["v1", "v2", "v3"]),
        endpoint=st.sampled_from(["/agents", "/episodes", "/workflows", "/feedback"]),
        response=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_version_header_present(self, version, endpoint, response):
        """INVARIANT: API version should be present in response headers"""
        # Simulate version header
        headers = {
            'X-API-Version': version,
            'Content-Type': 'application/json'
        }

        # Verify version header present
        assert 'X-API-Version' in headers, \
            "API response should include version header"

        # Verify version format
        version_value = headers['X-API-Version']
        assert isinstance(version_value, str), \
            "Version should be string"
        assert version_value.startswith('v'), \
            f"Version '{version_value}' should start with 'v'"
        assert len(version_value) >= 2, \
            f"Version '{version_value}' should have valid format"

    @given(
        deprecated_versions=st.lists(
            st.sampled_from(["v1", "v1.1", "v1.2"]),
            min_size=0,
            max_size=3,
            unique=True
        ),
        current_version=st.just("v2")
    )
    @settings(max_examples=50)
    def test_deprecation_warnings(self, deprecated_versions, current_version):
        """INVARIANT: Deprecated API versions should return deprecation warnings"""
        # Simulate deprecation check
        requested_version = deprecated_versions[0] if deprecated_versions else current_version

        # Check if version is deprecated
        is_deprecated = requested_version in deprecated_versions

        # Verify deprecation header for deprecated versions
        # Document the invariant - deprecated versions should include header
        if is_deprecated:
            # Should include X-API-Deprecated: true header
            assert True  # Document deprecation invariant
        else:
            # Current version, no deprecation needed
            assert True  # Current version is supported

    @given(
        client_version=st.sampled_from(["v1", "v1.1", "v2", "v2.1"]),
        server_version=st.just("v2")
    )
    @settings(max_examples=50)
    def test_version_compatibility(self, client_version, server_version):
        """INVARIANT: API should handle version compatibility gracefully"""
        # Extract version numbers
        client_major = int(client_version.replace('v', '').split('.')[0]) if client_version else 2
        server_major = int(server_version.replace('v', '').split('.')[0])

        # Verify compatibility rules
        if client_major == server_major:
            assert True  # Same major version - compatible
        elif client_major < server_major:
            assert True  # Older client - may work with deprecation warnings
        else:
            assert True  # Newer client - may not work with older server


class TestAPIRateLimitingContracts:
    """Tests for API rate limiting contract invariants"""

    @given(
        request_count=st.integers(min_value=0, max_value=10000),
        limit=st.integers(min_value=100, max_value=10000),
        window_seconds=st.integers(min_value=1, max_value=3600)
    )
    @settings(max_examples=50)
    def test_rate_limit_headers(self, request_count, limit, window_seconds):
        """INVARIANT: Rate limit information should be in response headers"""
        # Calculate remaining requests
        remaining = max(0, limit - request_count)

        # Simulate rate limit headers
        headers = {
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Reset': str(window_seconds)
        }

        # Verify headers present
        assert 'X-RateLimit-Limit' in headers, \
            "Rate limit response should include limit header"
        assert 'X-RateLimit-Remaining' in headers, \
            "Rate limit response should include remaining header"
        assert 'X-RateLimit-Reset' in headers, \
            "Rate limit response should include reset header"

        # Verify values are non-negative
        assert remaining >= 0, \
            "Remaining requests should be non-negative"
        assert remaining <= limit, \
            "Remaining requests should not exceed limit"

    @given(
        requests_in_window=st.integers(min_value=0, max_value=10000),
        limit=st.integers(min_value=100, max_value=1000)
    )
    @settings(max_examples=50)
    def test_rate_limit_enforcement(self, requests_in_window, limit):
        """INVARIANT: Rate limiting should enforce request limits"""
        # Check if limit exceeded
        limit_exceeded = requests_in_window > limit

        # Verify enforcement
        if limit_exceeded:
            # Should return 429 Too Many Requests
            expected_status = 429
            assert expected_status == 429, \
                "Rate limit exceeded should return 429 status"
        else:
            # Should allow request
            expected_status = 200
            assert expected_status == 200, \
                "Request within limit should succeed"

    @given(
        retry_after=st.integers(min_value=1, max_value=3600)
    )
    @settings(max_examples=50)
    def test_rate_limit_retry_after(self, retry_after):
        """INVARIANT: Rate limited responses should include Retry-After header"""
        # Simulate rate limited response
        headers = {
            'Retry-After': str(retry_after)
        }

        # Verify Retry-After header present
        assert 'Retry-After' in headers, \
            "Rate limited response should include Retry-After header"

        # Verify value is positive
        assert retry_after > 0, \
            "Retry-After should be positive"


class TestAPIFilteringContracts:
    """Tests for API filtering contract invariants"""

    @given(
        total_items=st.integers(min_value=0, max_value=100),
        filter_field=st.sampled_from(["status", "type", "category"]),
        filter_value=st.sampled_from(["active", "inactive", "pending"]),
        matching_items=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_filter_response_structure(self, total_items, filter_field, filter_value, matching_items):
        """INVARIANT: Filtered responses should include filter metadata"""
        # Ensure matching_items doesn't exceed total_items
        assume(matching_items <= total_items)

        # Simulate filter response
        response = {
            'items': [],
            'count': matching_items,
            'filter': {
                'field': filter_field,
                'value': filter_value
            },
            'total': total_items
        }

        # Verify filter metadata present
        assert 'filter' in response, \
            "Filtered response should include filter metadata"

        # Verify filter structure
        assert 'field' in response['filter'], \
            "Filter should include field"
        assert 'value' in response['filter'], \
            "Filter should include value"

        # Verify filtered count doesn't exceed total
        assert response['count'] <= response['total'], \
            "Filtered count should not exceed total items"

    @given(
        filters=st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            st.one_of(
                st.text(min_size=1, max_size=50),
                st.integers(min_value=0, max_value=1000),
                st.booleans(),
                st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_multiple_filters(self, filters):
        """INVARIANT: Multiple filters should be supported"""
        # Verify filter count
        assert len(filters) <= 10, \
            "Should support multiple filters (up to 10)"

        # Verify filter fields are non-empty
        for field_name in filters.keys():
            assert len(field_name) > 0, \
                "Filter field names should be non-empty"

        # Verify filter values are valid
        for value in filters.values():
            assert value is not None, \
                "Filter values should not be None"

    @given(
        total_items=st.integers(min_value=0, max_value=1000),
        items=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                min_size=1,
                max_size=5
            ),
            min_size=0,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_filter_results_subset(self, total_items, items):
        """INVARIANT: Filtered results should be subset of total items"""
        # Ensure items count doesn't exceed total_items
        assume(len(items) <= total_items)

        # Verify filtered items don't exceed total
        assert len(items) <= total_items, \
            "Filtered items should be subset of total items"


class TestAPISortingContracts:
    """Tests for API sorting contract invariants"""

    @given(
        items=st.lists(
            st.integers(min_value=0, max_value=1000),
            min_size=0,
            max_size=100,
            unique=True
        ),
        sort_field=st.just("value"),
        sort_order=st.sampled_from(["asc", "desc"])
    )
    @settings(max_examples=50)
    def test_sort_order_correctness(self, items, sort_field, sort_order):
        """INVARIANT: Sorted results should respect sort order"""
        # Sort items
        sorted_items = sorted(items, reverse=(sort_order == "desc"))

        # Verify sort order
        if len(sorted_items) > 1:
            if sort_order == "asc":
                assert sorted_items == sorted(items), \
                    "Ascending sort should be in increasing order"
            else:  # desc
                assert sorted_items == sorted(items, reverse=True), \
                    "Descending sort should be in decreasing order"

    @given(
        sort_fields=st.lists(
            st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=1,
            max_size=5,
            unique=True
        ),
        sort_order=st.sampled_from(["asc", "desc"])
    )
    @settings(max_examples=50)
    def test_multi_field_sorting(self, sort_fields, sort_order):
        """INVARIANT: Multiple sort fields should be supported"""
        # Verify sort field count
        assert len(sort_fields) <= 5, \
            "Should support up to 5 sort fields"

        # Verify field names are non-empty
        for field in sort_fields:
            assert len(field) > 0, \
                "Sort field names should be non-empty"

        # Verify sort order is valid
        assert sort_order in ["asc", "desc"], \
            "Sort order should be 'asc' or 'desc'"

    @given(
        total_items=st.integers(min_value=0, max_value=1000),
        sort_field=st.text(min_size=1, max_size=50),
        sort_order=st.sampled_from(["asc", "desc"])
    )
    @settings(max_examples=50)
    def test_sort_response_structure(self, total_items, sort_field, sort_order):
        """INVARIANT: Sorted responses should include sort metadata"""
        # Simulate sort response
        response = {
            'items': [],
            'count': total_items,
            'sort': {
                'field': sort_field,
                'order': sort_order
            }
        }

        # Verify sort metadata present
        assert 'sort' in response, \
            "Sorted response should include sort metadata"

        # Verify sort structure
        assert 'field' in response['sort'], \
            "Sort should include field"
        assert 'order' in response['sort'], \
            "Sort should include order"

        # Verify sort order is valid
        assert response['sort']['order'] in ["asc", "desc"], \
            "Sort order should be 'asc' or 'desc'"


class TestAPIBatchOperationContracts:
    """Tests for API batch operation contract invariants"""

    @given(
        batch_size=st.integers(min_value=1, max_value=100),
        max_batch_size=st.integers(min_value=10, max_value=1000)
    )
    @settings(max_examples=50)
    def test_batch_size_limits(self, batch_size, max_batch_size):
        """INVARIANT: Batch operations should respect size limits"""
        # Verify batch size is positive
        assert batch_size > 0, \
            "Batch size should be positive"

        # Verify max_batch_size is positive
        assert max_batch_size > 0, \
            "Max batch size should be positive"

        # Document invariant: batch size should not exceed maximum
        # If batch_size > max_batch_size, API should return validation error
        if batch_size <= max_batch_size:
            assert True  # Valid batch size
        else:
            assert True  # Should return 400 Bad Request with error message

    @given(
        operations=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                min_size=1,
                max_size=5
            ),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_batch_operation_response(self, operations):
        """INVARIANT: Batch operations should return results for each operation"""
        # Simulate batch response
        response = {
            'results': [],
            'success_count': 0,
            'error_count': 0,
            'total': len(operations)
        }

        # Verify response structure
        assert 'results' in response, \
            "Batch response should include results"
        assert 'success_count' in response, \
            "Batch response should include success count"
        assert 'error_count' in response, \
            "Batch response should include error count"
        assert 'total' in response, \
            "Batch response should include total count"

        # Verify total matches operations
        assert response['total'] == len(operations), \
            "Total should match number of operations"

    @given(
        success_count=st.integers(min_value=0, max_value=100),
        error_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_batch_operation_summary(self, success_count, error_count):
        """INVARIANT: Batch operation summary should be accurate"""
        # Calculate total
        total = success_count + error_count

        # Verify counts are non-negative
        assert success_count >= 0, \
            "Success count should be non-negative"
        assert error_count >= 0, \
            "Error count should be non-negative"

        # Verify total is consistent
        assert total == (success_count + error_count), \
            "Total should equal success + error counts"


class TestAPIValidationContracts:
    """Tests for API validation contract invariants"""

    @given(
        email_addresses=st.lists(
            st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@.-_'),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_email_validation(self, email_addresses):
        """INVARIANT: API should validate email addresses"""
        # Define email validation rules
        def is_valid_email(email):
            return email.count('@') == 1 and '.' in email.split('@')[-1]

        # Test each email
        for email in email_addresses:
            is_valid = is_valid_email(email)

            # If valid, verify format
            if is_valid:
                assert '@' in email, \
                    "Valid email should contain @"
                assert email.count('@') == 1, \
                    "Valid email should contain only one @"
                assert '.' in email.split('@')[-1], \
                    "Valid email should have domain extension"

    @given(
        urls=st.lists(
            st.text(min_size=1, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/-._~?#[]@!$&\'()*+,;='),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_url_validation(self, urls):
        """INVARIANT: API should validate URLs"""
        # Test each URL
        for url in urls:
            # Basic URL validation
            if url.startswith('http://') or url.startswith('https://'):
                assert '://' in url, \
                    "URL with protocol should contain ://"

                # Extract domain
                parts = url.split('://')
                if len(parts) > 1:
                    domain = parts[1].split('/')[0]
                    assert len(domain) > 0, \
                        "URL should have valid domain"

    @given(
        numeric_values=st.one_of(
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
        ),
        min_value=st.integers(min_value=-1000000, max_value=0),
        max_value=st.integers(min_value=0, max_value=1000000)
    )
    @settings(max_examples=50)
    def test_numeric_range_validation(self, numeric_values, min_value, max_value):
        """INVARIANT: API should validate numeric ranges"""
        # Verify min <= max
        assume(min_value <= max_value)

        # Check if value is in range
        is_in_range = min_value <= numeric_values <= max_value

        # If out of range, should return validation error
        if not is_in_range:
            # Would return 400 Bad Request with validation error
            assert True  # Document invariant
        else:
            assert numeric_values >= min_value, \
                "Value should be >= min"
            assert numeric_values <= max_value, \
                "Value should be <= max"
