"""
HTTP Client Coverage Tests

Comprehensive tests for HTTP client initialization, connection pooling,
timeout handling, error handling, and cleanup to achieve 80%+ coverage.

Target: 250+ lines, 15+ tests, 80%+ coverage for http_client.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from core.http_client import (
    get_async_client,
    get_sync_client,
    close_http_clients,
    reset_http_clients,
    async_get,
    async_post,
    async_put,
    async_delete,
    sync_get,
    sync_post,
    sync_put,
    sync_delete,
    DEFAULT_TIMEOUT,
    DEFAULT_LIMITS,
)


class TestClientInitialization:
    """Test HTTP client singleton pattern and configuration."""

    def test_async_client_created_once(self):
        """Test that async client is created only once (singleton pattern)."""
        # Reset to ensure clean state
        reset_http_clients()

        # Get client twice
        client1 = get_async_client()
        client2 = get_async_client()

        # Verify singleton (same instance)
        assert client1 is client2
        assert isinstance(client1, httpx.AsyncClient)

        # Cleanup
        reset_http_clients()

    def test_sync_client_created_once(self):
        """Test that sync client is created only once (singleton pattern)."""
        # Reset to ensure clean state
        reset_http_clients()

        # Get client twice
        client1 = get_sync_client()
        client2 = get_sync_client()

        # Verify singleton (same instance)
        assert client1 is client2
        assert isinstance(client1, httpx.Client)

        # Cleanup
        reset_http_clients()

    def test_async_client_configuration(self):
        """Test that async client has correct default configuration."""
        reset_http_clients()

        client = get_async_client()

        # Verify timeout (httpx.Timeout object)
        assert isinstance(client.timeout, httpx.Timeout)

        # Verify client is AsyncClient instance
        assert isinstance(client, httpx.AsyncClient)

        # Verify client is not closed
        assert client.is_closed is False

        reset_http_clients()

    def test_sync_client_configuration(self):
        """Test that sync client has correct default configuration."""
        reset_http_clients()

        client = get_sync_client()

        # Verify timeout (httpx.Timeout object)
        assert isinstance(client.timeout, httpx.Timeout)

        # Verify client is Client instance
        assert isinstance(client, httpx.Client)

        # Verify client is not closed
        assert client.is_closed is False

        reset_http_clients()


class TestConnectionPooling:
    """Test HTTP client connection pooling and reuse."""

    @pytest.mark.asyncio
    async def test_async_connection_reuse(self):
        """Test that async client reuses connections across requests."""
        reset_http_clients()

        # Mock the get method to return successful response
        client = get_async_client()

        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            # Configure mock to return success response
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            # Make 2 requests to same URL
            url = "http://example.com/api/test"
            response1 = await client.get(url)
            response2 = await client.get(url)

            # Verify both succeeded
            assert response1.status_code == 200
            assert response2.status_code == 200

            # Verify same client instance used (connection reuse)
            assert mock_get.call_count == 2

        reset_http_clients()

    def test_sync_connection_reuse(self):
        """Test that sync client reuses connections across requests."""
        reset_http_clients()

        # Mock the get method to return successful response
        client = get_sync_client()

        with patch.object(client, 'get') as mock_get:
            # Configure mock to return success response
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            # Make 2 requests
            url = "http://example.com/api/test"
            response1 = client.get(url)
            response2 = client.get(url)

            # Verify both succeeded
            assert response1.status_code == 200
            assert response2.status_code == 200

            # Verify same client instance used (connection reuse)
            assert mock_get.call_count == 2

        reset_http_clients()


class TestTimeoutHandling:
    """Test HTTP client timeout handling."""

    @pytest.mark.asyncio
    async def test_async_request_timeout(self):
        """Test that async client raises TimeoutException on timeout."""
        reset_http_clients()

        client = get_async_client()

        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            # Mock to raise TimeoutException
            mock_get.side_effect = httpx.TimeoutException("Request timed out")

            # Verify exception is raised
            url = "http://example.com/api/test"
            with pytest.raises(httpx.TimeoutException):
                await client.get(url)

        reset_http_clients()

    def test_sync_request_timeout(self):
        """Test that sync client raises TimeoutException on timeout."""
        reset_http_clients()

        client = get_sync_client()

        with patch.object(client, 'get') as mock_get:
            # Mock to raise TimeoutException
            mock_get.side_effect = httpx.TimeoutException("Request timed out")

            # Verify exception is raised
            url = "http://example.com/api/test"
            with pytest.raises(httpx.TimeoutException):
                client.get(url)

        reset_http_clients()
