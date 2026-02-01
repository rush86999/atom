"""
Base Integration Class for ATOM Platform
Provides common functionality to reduce code duplication across integrations
"""

import abc
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from shared.logging_utils import get_integration_logger, log_integration_error


class IntegrationBase(abc.ABC):
    """
    Abstract base class for all service integrations
    Provides common functionality and enforces consistent patterns
    """

    def __init__(self, integration_name: str, user_id: Optional[str] = None):
        """
        Initialize integration

        Args:
            integration_name: Name of the integration service
            user_id: Optional user identifier for logging
        """
        self.integration_name = integration_name
        self.user_id = user_id
        self.logger = get_integration_logger(integration_name, user_id)
        self._cache = {}
        self._rate_limit_remaining = None
        self._rate_limit_reset = None

    @abc.abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str, scopes: List[str]) -> str:
        """
        Generate OAuth authorization URL

        Args:
            redirect_uri: Callback URL
            state: CSRF token
            scopes: List of permission scopes

        Returns:
            Authorization URL
        """
        pass

    @abc.abstractmethod
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code
            redirect_uri: Callback URL

        Returns:
            Token response
        """
        pass

    @abc.abstractmethod
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            Token response
        """
        pass

    @abc.abstractmethod
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information

        Args:
            access_token: Access token

        Returns:
            User information
        """
        pass

    # Common utility methods
    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 3,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Make HTTP request with common error handling and retry logic

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            headers: Request headers
            data: Request body data
            params: Query parameters
            retry_count: Number of retry attempts

        Returns:
            Tuple of (success, response_data)
        """
        import requests

        headers = headers or {}
        data = data or {}
        params = params or {}

        # Add common headers
        headers.setdefault("User-Agent", f"ATOM-Integration/{self.integration_name}")
        headers.setdefault("Accept", "application/json")

        for attempt in range(retry_count):
            try:
                self.logger.info(
                    f"Making {method} request to {url}",
                    {
                        "attempt": attempt + 1,
                        "params": params,
                        "headers": {k: "***" for k in headers.keys()},
                    },
                )

                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if data and method in ["POST", "PUT", "PATCH"] else None,
                    params=params,
                    timeout=30,
                )

                # Handle rate limiting
                self._handle_rate_limits(response)

                if response.status_code == 200:
                    response_data = response.json()
                    self.logger.info(
                        f"Request successful",
                        {
                            "status_code": response.status_code,
                            "response_size": len(response.text),
                        },
                    )
                    return True, response_data

                elif response.status_code in [401, 403]:
                    self.logger.warning(
                        f"Authentication failed",
                        {
                            "status_code": response.status_code,
                            "response": response.text,
                        },
                    )
                    return False, {
                        "error": "authentication_failed",
                        "details": response.text,
                    }

                elif response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.warning(
                        f"Rate limited, waiting {retry_after} seconds",
                        {"retry_after": retry_after},
                    )
                    time.sleep(retry_after)
                    continue

                else:
                    self.logger.error(
                        f"Request failed with status {response.status_code}",
                        {
                            "status_code": response.status_code,
                            "response": response.text,
                        },
                    )
                    return False, {
                        "error": "request_failed",
                        "status_code": response.status_code,
                        "details": response.text,
                    }

            except requests.exceptions.Timeout:
                self.logger.error(f"Request timeout on attempt {attempt + 1}")
                if attempt == retry_count - 1:
                    return False, {"error": "timeout"}

            except requests.exceptions.ConnectionError:
                self.logger.error(f"Connection error on attempt {attempt + 1}")
                if attempt == retry_count - 1:
                    return False, {"error": "connection_error"}

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request exception: {e}")
                if attempt == retry_count - 1:
                    return False, {"error": "request_exception", "details": str(e)}

            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                return False, {"error": "json_decode_error", "details": str(e)}

            # Exponential backoff
            if attempt < retry_count - 1:
                sleep_time = 2**attempt
                self.logger.info(f"Retrying in {sleep_time} seconds")
                time.sleep(sleep_time)

        return False, {"error": "max_retries_exceeded"}

    def _handle_rate_limits(self, response) -> None:
        """Handle rate limit headers from API responses"""
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset")

        if rate_limit_remaining:
            self._rate_limit_remaining = int(rate_limit_remaining)

        if rate_limit_reset:
            self._rate_limit_reset = int(rate_limit_reset)

        if self._rate_limit_remaining == 0:
            self.logger.warning(
                "Rate limit reached",
                {
                    "rate_limit_remaining": self._rate_limit_remaining,
                    "rate_limit_reset": self._rate_limit_reset,
                },
            )

    def _build_oauth_url(
        self,
        base_url: str,
        client_id: str,
        redirect_uri: str,
        state: str,
        scopes: List[str],
        additional_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build OAuth authorization URL with common parameters

        Args:
            base_url: OAuth authorization endpoint
            client_id: OAuth client ID
            redirect_uri: Callback URL
            state: CSRF token
            scopes: List of permission scopes
            additional_params: Additional query parameters

        Returns:
            Complete OAuth URL
        """
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(scopes),
        }

        if additional_params:
            params.update(additional_params)

        return f"{base_url}?{urlencode(params)}"

    def _cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache:
            cached_data = self._cache[key]
            if cached_data["expires"] > time.time():
                return cached_data["value"]
            else:
                del self._cache[key]
        return None

    def _cache_set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL"""
        self._cache[key] = {
            "value": value,
            "expires": time.time() + ttl,
        }

    def _validate_scopes(
        self, required_scopes: List[str], available_scopes: List[str]
    ) -> bool:
        """
        Validate that required scopes are available

        Args:
            required_scopes: List of required scopes
            available_scopes: List of available scopes

        Returns:
            True if all required scopes are available
        """
        missing_scopes = set(required_scopes) - set(available_scopes)
        if missing_scopes:
            self.logger.warning(
                "Missing required scopes",
                {
                    "missing_scopes": list(missing_scopes),
                    "available_scopes": available_scopes,
                },
            )
            return False
        return True

    def _handle_error(
        self, error: Exception, operation: str, extra_data: Optional[Dict] = None
    ) -> None:
        """
        Standardized error handling

        Args:
            error: Exception that occurred
            operation: Description of the operation that failed
            extra_data: Additional context data
        """
        log_integration_error(
            integration_name=self.integration_name,
            error_message=f"Operation failed: {operation}",
            exception=error,
            user_id=self.user_id,
            extra_data=extra_data,
        )

    def get_rate_limit_info(self) -> Dict[str, Optional[int]]:
        """Get current rate limit information"""
        return {
            "remaining": self._rate_limit_remaining,
            "reset": self._rate_limit_reset,
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on integration

        Returns:
            Health status information
        """
        try:
            # Basic health check - can be overridden by subclasses
            return {
                "status": "healthy",
                "integration": self.integration_name,
                "timestamp": time.time(),
                "rate_limit": self.get_rate_limit_info(),
            }
        except Exception as e:
            self._handle_error(e, "health_check")
            return {
                "status": "unhealthy",
                "integration": self.integration_name,
                "error": str(e),
                "timestamp": time.time(),
            }

    def cleanup(self) -> None:
        """Cleanup resources"""
        self._cache.clear()
        self.logger.info("Integration cleanup completed")


class PaginatedIntegrationBase(IntegrationBase):
    """
    Base class for integrations that support pagination
    """

    @abc.abstractmethod
    def get_items_page(
        self, access_token: str, page: int = 1, page_size: int = 50, **filters
    ) -> Dict[str, Any]:
        """
        Get a page of items

        Args:
            access_token: Access token
            page: Page number
            page_size: Number of items per page
            filters: Additional filter parameters

        Returns:
            Page of items with pagination metadata
        """
        pass

    def get_all_items(
        self, access_token: str, page_size: int = 50, max_pages: int = 100, **filters
    ) -> List[Any]:
        """
        Get all items by paginating through all pages

        Args:
            access_token: Access token
            page_size: Number of items per page
            max_pages: Maximum number of pages to fetch
            filters: Additional filter parameters

        Returns:
            List of all items
        """
        all_items = []
        current_page = 1

        while current_page <= max_pages:
            self.logger.info(f"Fetching page {current_page}", {"page": current_page})

            success, page_data = self.get_items_page(
                access_token=access_token,
                page=current_page,
                page_size=page_size,
                **filters,
            )

            if not success:
                self.logger.error(f"Failed to fetch page {current_page}")
                break

            items = page_data.get("items", [])
            all_items.extend(items)

            # Check if we've reached the last page
            if len(items) < page_size:
                self.logger.info(
                    "Reached last page",
                    {
                        "total_items": len(all_items),
                        "pages_processed": current_page,
                    },
                )
                break

            current_page += 1

            # Rate limiting protection
            rate_info = self.get_rate_limit_info()
            if rate_info["remaining"] and rate_info["remaining"] < 10:
                self.logger.warning(
                    "Approaching rate limit, paging stopped",
                    {"rate_limit_remaining": rate_info["remaining"]},
                )
                break

        return all_items
