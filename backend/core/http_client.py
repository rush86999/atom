"""
Shared HTTP Client

Provides standardized HTTP client configuration and usage across the codebase.
Uses httpx for both sync and async operations with connection pooling,
timeouts, and proper resource cleanup.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
DEFAULT_LIMITS = httpx.Limits(
    max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "100")),
    max_keepalive_connections=int(os.getenv("HTTP_MAX_KEEPALIVE", "20"))
)

# Shared clients (lazy initialization)
_async_client: Optional[httpx.AsyncClient] = None
_sync_client: Optional[httpx.Client] = None


def get_async_client() -> httpx.AsyncClient:
    """
    Get or create the shared async HTTP client.

    This provides connection pooling and reuse across all async HTTP requests.
    The client is created on first use and should be closed via close_http_clients()
    during application shutdown.

    Returns:
        Shared httpx.AsyncClient instance

    Example:
        from core.http_client import get_async_client

        async def fetch_data(url: str):
            client = get_async_client()
            response = await client.get(url)
            return response.json()
    """
    global _async_client
    if _async_client is None:
        timeout = httpx.Timeout(DEFAULT_TIMEOUT)
        _async_client = httpx.AsyncClient(
            timeout=timeout,
            limits=DEFAULT_LIMITS,
            http2=True,  # Enable HTTP/2 support
            verify=True  # Verify SSL certificates
        )
        logger.debug("Created shared async HTTP client")
    return _async_client


def get_sync_client() -> httpx.Client:
    """
    Get or create the shared sync HTTP client.

    This provides connection pooling and reuse across all synchronous HTTP requests.
    The client is created on first use and should be closed via close_http_clients()
    during application shutdown.

    Returns:
        Shared httpx.Client instance

    Example:
        from core.http_client import get_sync_client

        def fetch_data(url: str):
            client = get_sync_client()
            response = client.get(url)
            return response.json()
    """
    global _sync_client
    if _sync_client is None:
        timeout = httpx.Timeout(DEFAULT_TIMEOUT)
        _sync_client = httpx.Client(
            timeout=timeout,
            limits=DEFAULT_LIMITS,
            http2=True,  # Enable HTTP/2 support
            verify=True  # Verify SSL certificates
        )
        logger.debug("Created shared sync HTTP client")
    return _sync_client


async def close_http_clients():
    """
    Close all HTTP clients (call during application shutdown).

    This should be called in your application shutdown handler to properly
    close all connections and release resources.

    Example:
        from fastapi import FastAPI
        from core.http_client import close_http_clients

        app = FastAPI()

        @app.on_event("shutdown")
        async def shutdown_event():
            await close_http_clients()
    """
    global _async_client, _sync_client

    if _async_client:
        await _async_client.aclose()
        _async_client = None
        logger.info("Closed async HTTP client")

    if _sync_client:
        _sync_client.close()
        _sync_client = None
        logger.info("Closed sync HTTP client")


def reset_http_clients():
    """
    Reset HTTP clients (useful for testing or reconnection).

    This closes existing clients and allows new ones to be created on next access.
    """
    global _async_client, _sync_client

    if _async_client:
        try:
            import asyncio
            # Try to close if there's a running loop
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.create_task(_async_client.aclose())
                else:
                    asyncio.run(_async_client.aclose())
            except RuntimeError:
                # No event loop, close synchronously
                _async_client.close()
        except Exception as e:
            logger.warning(f"Error closing async client during reset: {e}")
        _async_client = None

    if _sync_client:
        try:
            _sync_client.close()
        except Exception as e:
            logger.warning(f"Error closing sync client during reset: {e}")
        _sync_client = None

    logger.info("Reset HTTP clients")


# Convenience functions for simple requests

async def async_get(url: str, **kwargs) -> httpx.Response:
    """
    Perform an async GET request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.get()

    Returns:
        httpx.Response object
    """
    client = get_async_client()
    return await client.get(url, **kwargs)


async def async_post(url: str, **kwargs) -> httpx.Response:
    """
    Perform an async POST request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.post()

    Returns:
        httpx.Response object
    """
    client = get_async_client()
    return await client.post(url, **kwargs)


async def async_put(url: str, **kwargs) -> httpx.Response:
    """
    Perform an async PUT request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.put()

    Returns:
        httpx.Response object
    """
    client = get_async_client()
    return await client.put(url, **kwargs)


async def async_delete(url: str, **kwargs) -> httpx.Response:
    """
    Perform an async DELETE request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.delete()

    Returns:
        httpx.Response object
    """
    client = get_async_client()
    return await client.delete(url, **kwargs)


def sync_get(url: str, **kwargs) -> httpx.Response:
    """
    Perform a synchronous GET request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.get()

    Returns:
        httpx.Response object
    """
    client = get_sync_client()
    return client.get(url, **kwargs)


def sync_post(url: str, **kwargs) -> httpx.Response:
    """
    Perform a synchronous POST request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.post()

    Returns:
        httpx.Response object
    """
    client = get_sync_client()
    return client.post(url, **kwargs)


def sync_put(url: str, **kwargs) -> httpx.Response:
    """
    Perform a synchronous PUT request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.put()

    Returns:
        httpx.Response object
    """
    client = get_sync_client()
    return client.put(url, **kwargs)


def sync_delete(url: str, **kwargs) -> httpx.Response:
    """
    Perform a synchronous DELETE request using the shared client.

    Args:
        url: URL to request
        **kwargs: Additional arguments passed to client.delete()

    Returns:
        httpx.Response object
    """
    client = get_sync_client()
    return client.delete(url, **kwargs)


__all__ = [
    "get_async_client",
    "get_sync_client",
    "close_http_clients",
    "reset_http_clients",
    "async_get",
    "async_post",
    "async_put",
    "async_delete",
    "sync_get",
    "sync_post",
    "sync_put",
    "sync_delete",
]
