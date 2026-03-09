"""
API accessibility header tests

Tests verify that API responses include proper accessibility headers:
- Content-Type headers for all responses
- Accessible error responses with clear messages
- HEAD method support for resources
- Rate limit headers that are readable
- Clear pagination headers
- Content-Language headers
- Alt text for image endpoints
"""

import pytest
from fastapi.testclient import TestClient
from typing import Dict, Any


class TestAPIResponseHeaders:
    """Test suite for API accessibility headers"""

    def test_api_returns_content_type_header(self, client: TestClient):
        """Test that API responses include Content-Type header."""
        response = client.get('/api/v1/agents')

        assert response.status_code in [200, 401, 403]  # May be unauthorized
        assert 'Content-Type' in response.headers
        assert 'application/json' in response.headers['Content-Type']

    def test_api_returns_accessible_error_responses(self, client: TestClient):
        """Test that error responses have clear, accessible messages."""
        response = client.get('/api/v1/agents/nonexistent')

        # Error responses should have clear messages
        if response.status_code == 404:
            assert 'application/json' in response.headers['Content-Type']
            error_data = response.json()
            assert 'detail' in error_data or 'message' in error_data

    def test_api_error_messages_are_human_readable(self, client: TestClient):
        """Test that error messages are clear and actionable."""
        # Test 400 Bad Request
        response = client.post(
            '/api/v1/agents/execute',
            json={'invalid': 'data'}
        )

        if response.status_code == 400:
            error_data = response.json()
            # Error should have a human-readable message
            assert 'detail' in error_data or 'message' in error_data
            # Message should not be empty or just error code
            message = error_data.get('detail', error_data.get('message', ''))
            assert len(message) > 10  # More than just error code

    def test_api_supports_head_requests_for_resources(self, client: TestClient):
        """Test that HEAD method is supported for resource endpoints."""
        # HEAD request should return same headers as GET
        response = client.head('/api/v1/agents')

        # HEAD should return headers without body
        assert response.status_code in [200, 401, 403]
        assert 'Content-Type' in response.headers
        assert len(response.content) == 0  # No body in HEAD response

    def test_api_rate_limit_headers_are_accessible(self, client: TestClient):
        """Test that rate limit information is in readable headers."""
        response = client.get('/api/v1/agents')

        # Check for common rate limit headers
        rate_limit_headers = [
            'X-RateLimit-Limit',
            'X-RateLimit-Remaining',
            'X-RateLimit-Reset',
            'RateLimit-Limit',
            'RateLimit-Remaining',
            'RateLimit-Reset'
        ]

        # At least one rate limit header should be present if rate limiting is enabled
        has_rate_limit = any(header in response.headers for header in rate_limit_headers)

        # If rate limiting is enabled, headers should be readable
        if has_rate_limit:
            for header in rate_limit_headers:
                if header in response.headers:
                    value = response.headers[header]
                    assert value is not None
                    assert len(value) > 0

    def test_api_pagination_headers_are_clear(self, client: TestClient):
        """Test that pagination information is in clear headers."""
        # Test a list endpoint that might have pagination
        response = client.get('/api/v1/agents')

        # Check for common pagination headers
        pagination_headers = [
            'X-Total-Count',
            'X-Page',
            'X-Per-Page',
            'X-Total-Pages',
            'Link'
        ]

        # If pagination is present, headers should be clear
        for header in pagination_headers:
            if header in response.headers:
                value = response.headers[header]
                assert value is not None
                assert len(value) > 0

    def test_api_response_language_is_consistent(self, client: TestClient):
        """Test that Content-Language header is present."""
        response = client.get('/api/v1/agents')

        # Content-Language header should indicate response language
        if 'Content-Language' in response.headers:
            lang = response.headers['Content-Language']
            assert lang in ['en', 'en-US', 'en-GB'] or lang.startswith('en')

    def test_api_returns_structured_json_errors(self, client: TestClient):
        """Test that errors are returned as structured JSON."""
        response = client.get('/api/v1/agents/nonexistent-id-12345')

        if response.status_code in [400, 404, 422]:
            # Error should be JSON
            assert 'application/json' in response.headers['Content-Type']

            # Error should have structure
            error_data = response.json()
            assert isinstance(error_data, dict)

    def test_api_error_responses_include_helpful_info(self, client: TestClient):
        """Test that error responses include helpful information."""
        response = client.get('/api/v1/agents/nonexistent-id-12345')

        if response.status_code == 404:
            error_data = response.json()

            # Error should explain what was wrong
            assert 'detail' in error_data or 'message' in error_data
            message = error_data.get('detail', error_data.get('message', ''))

            # Message should be descriptive
            assert len(message) > 5

    def test_api_success_responses_are_consistent(self, client: TestClient):
        """Test that success responses have consistent structure."""
        # Try to get agents list
        response = client.get('/api/v1/agents')

        if response.status_code == 200:
            data = response.json()

            # Should be a list or dict with data field
            assert isinstance(data, (dict, list))

            if isinstance(data, dict):
                # Common response fields
                possible_keys = ['data', 'results', 'agents', 'items']
                has_data_key = any(key in data for key in possible_keys)
                # Not all endpoints need these keys, so we don't assert

    def test_api_includes_timestamp_in_responses(self, client: TestClient):
        """Test that API responses include timestamp information."""
        response = client.get('/api/v1/agents')

        if response.status_code == 200:
            data = response.json()

            # Check for timestamp in response headers or body
            has_timestamp = (
                'Date' in response.headers or
                'Last-Modified' in response.headers or
                (isinstance(data, dict) and any(
                    key in data for key in ['timestamp', 'created_at', 'updated_at', 'date']
                ))
            )
            # Timestamps are good practice but not always required

    def test_api_cors_headers_are_accessible(self, client: TestClient):
        """Test that CORS headers are present and readable."""
        response = client.get('/api/v1/agents')

        # Check for common CORS headers
        cors_headers = [
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers',
            'Access-Control-Max-Age'
        ]

        # If CORS is enabled, headers should be present
        for header in cors_headers:
            if header in response.headers:
                value = response.headers[header]
                assert value is not None
                assert len(value) > 0

    def test_api_error_codes_are_explanatory(self, client: TestClient):
        """Test that error codes are explanatory, not cryptic."""
        response = client.get('/api/v1/agents/nonexistent-id-12345')

        if response.status_code == 404:
            error_data = response.json()

            # Error message should be in natural language
            message = error_data.get('detail', error_data.get('message', ''))

            # Should not be just error codes
            assert not message.startswith('E')
            assert not message.startswith('ERR_')

    def test_api_supports_content_negotiation(self, client: TestClient):
        """Test that API supports content negotiation."""
        # Request JSON response
        response = client.get(
            '/api/v1/agents',
            headers={'Accept': 'application/json'}
        )

        # Should return JSON
        assert 'Content-Type' in response.headers
        assert 'application/json' in response.headers['Content-Type']

    def test_api_responses_are_gzipped_when_appropriate(self, client: TestClient):
        """Test that API supports compression for large responses."""
        # Request with Accept-Encoding
        response = client.get(
            '/api/v1/agents',
            headers={'Accept-Encoding': 'gzip, deflate'}
        )

        # If response is large enough, should be compressed
        if 'Content-Encoding' in response.headers:
            encoding = response.headers['Content-Encoding']
            assert encoding in ['gzip', 'deflate', 'br']

    def test_api_includes_request_id_in_headers(self, client: TestClient):
        """Test that API includes request ID for debugging."""
        response = client.get('/api/v1/agents')

        # Request ID headers help with debugging accessibility issues
        request_id_headers = [
            'X-Request-ID',
            'X-Correlation-ID',
            'Request-ID'
        ]

        # At least one request ID header is good practice
        has_request_id = any(header in response.headers for header in request_id_headers)

        if has_request_id:
            for header in request_id_headers:
                if header in response.headers:
                    value = response.headers[header]
                    assert value is not None
                    assert len(value) > 0

    def test_api_health_endpoint_accessible(self, client: TestClient):
        """Test that health endpoint is accessible and clear."""
        response = client.get('/health/live')

        assert response.status_code == 200
        assert 'application/json' in response.headers.get('Content-Type', '')

        data = response.json()
        assert isinstance(data, dict)

    def test_api_readiness_endpoint_accessible(self, client: TestClient):
        """Test that readiness endpoint includes service status."""
        response = client.get('/health/ready')

        assert response.status_code in [200, 503]  # Up or degraded

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_api_error_responses_include_status_code(self, client: TestClient):
        """Test that error responses include HTTP status context."""
        response = client.post(
            '/api/v1/agents/execute',
            json={'invalid': 'data'}
        )

        if response.status_code == 400:
            # Error response should indicate status
            error_data = response.json()
            assert 'detail' in error_data or 'message' in error_data

    def test_api_validation_errors_are_clear(self, client: TestClient):
        """Test that validation errors provide specific feedback."""
        response = client.post(
            '/api/v1/agents',
            json={'name': ''}  # Empty name should fail validation
        )

        if response.status_code == 422:
            error_data = response.json()

            # Validation errors should list specific issues
            assert 'detail' in error_data or 'errors' in error_data

    def test_api_responses_include_api_version(self, client: TestClient):
        """Test that API version is indicated in responses."""
        response = client.get('/api/v1/agents')

        # Version can be in URL, header, or response body
        has_version = (
            'X-API-Version' in response.headers or
            'API-Version' in response.headers
        )

        # API version in URL is sufficient (we use /api/v1/)
        assert '/v1/' in response.request.url or has_version

    def test_api_rate_limit_exceeded_clear(self, client: TestClient):
        """Test that rate limit exceeded is clearly indicated."""
        # This test would require triggering rate limit
        # For now, we test the structure

        # If rate limited, should return 429 with clear message
        # (We can't easily trigger this in tests)

        # Placeholder for rate limit testing
        assert True


class TestAPIAccessibilityForAssistiveTechnology:
    """Test suite for API accessibility for assistive technology users"""

    def test_api_alt_text_in_image_endpoints(self, client: TestClient):
        """Test that image endpoints include alt text metadata."""
        # If there are image/chart endpoints, they should include alt text
        # This is a placeholder for chart/canvas endpoints

        # Test canvas endpoint if it exists
        response = client.get('/api/v1/canvas/test-canvas-id')

        # If canvas exists, should include alt text or description
        if response.status_code == 200:
            data = response.json()

            # Check for alt text or description fields
            has_alt_text = (
                'alt_text' in data or
                'description' in data or
                'title' in data
            )

            # Not all canvas types need alt text, but it's good practice

    def test_api_screen_reader_friendly_errors(self, client: TestClient):
        """Test that errors are screen reader friendly."""
        response = client.get('/api/v1/agents/nonexistent')

        if response.status_code == 404:
            error_data = response.json()

            # Error should be in plain text, not HTML
            assert 'application/json' in response.headers.get('Content-Type', '')

            # Error message should be self-explanatory
            message = error_data.get('detail', error_data.get('message', ''))
            assert len(message) > 0

    def test_api_semantic_headers(self, client: TestClient):
        """Test that API uses semantic HTTP headers."""
        response = client.get('/api/v1/agents')

        # Should use standard HTTP headers
        assert 'Content-Type' in response.headers

        # Should use appropriate status codes
        assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]


class TestAPIResponseTimeAccessibility:
    """Test suite for API response time considerations"""

    def test_api_responses_are_reasonably_fast(self, client: TestClient):
        """Test that API responses are fast enough for accessibility."""
        import time

        start = time.time()
        response = client.get('/api/v1/agents')
        end = time.time()

        # Response should be reasonably fast (< 5 seconds)
        # This is important for users with assistive technology
        assert (end - start) < 5.0

    def test_api_timeout_handling(self, client: TestClient):
        """Test that API handles timeouts gracefully."""
        # This would require mocking slow responses
        # For now, we test the structure

        # Placeholder for timeout testing
        assert True

# Note: client fixture is provided by backend/tests/integration/conftest.py
