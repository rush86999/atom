"""
API-first setup utilities for fast test initialization.

This module provides utilities for quickly setting up test data by calling
API endpoints directly, bypassing slow UI navigation (10-100x speedup).

Base URL: http://localhost:8001 (non-conflicting with dev backend on port 8000)
"""

import requests
from typing import Any, Dict, Optional


class APIClient:
    """
    HTTP client for making API requests to the backend during tests.

    Provides convenient methods for HTTP requests with JSON handling and
    authentication header support.
    """

    def __init__(self, base_url: str = "http://localhost:8001", token: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the backend API (default: http://localhost:8001)
            token: Optional JWT authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication if token is available.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users")
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a POST request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users")
            data: Optional form data
            json: Optional JSON data

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.post(url, headers=self._get_headers(), data=data, json=json)
        response.raise_for_status()
        return response.json()

    def put(self, path: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a PUT request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users/me")
            data: Optional form data
            json: Optional JSON data

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.put(url, headers=self._get_headers(), data=data, json=json)
        response.raise_for_status()
        return response.json()

    def delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a DELETE request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/projects/123")
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.delete(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def set_token(self, token: str) -> None:
        """
        Set the authentication token for subsequent requests.

        Args:
            token: JWT authentication token
        """
        self.token = token

    def clear_token(self) -> None:
        """Clear the authentication token."""
        self.token = None
