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


# ============================================================================
# User Setup Functions
# ============================================================================

def create_test_user(client: APIClient, email: str, password: str, first_name: str = "Test", last_name: str = "User") -> Dict[str, Any]:
    """
    Create a test user via API.

    Args:
        client: APIClient instance
        email: User email
        password: User password
        first_name: User first name (default: "Test")
        last_name: User last name (default: "User")

    Returns:
        User data response from API

    Raises:
        requests.HTTPError: If user creation fails
    """
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name
        }
    )


def authenticate_user(client: APIClient, email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user and get access token.

    Args:
        client: APIClient instance
        email: User email
        password: User password

    Returns:
        Authentication response with access_token

    Raises:
        requests.HTTPError: If authentication fails
    """
    return client.post(
        "/api/auth/login",
        json={
            "username": email,
            "password": password
        }
    )


def get_test_user_token(client: APIClient, email: str, password: str) -> str:
    """
    Get JWT token for a test user.

    Args:
        client: APIClient instance
        email: User email
        password: User password

    Returns:
        JWT access token

    Raises:
        requests.HTTPError: If authentication fails
    """
    response = authenticate_user(client, email, password)
    return response["access_token"]


def set_authenticated_session(page, token: str) -> None:
    """
    Set JWT token in localStorage for Playwright page.

    This authenticates the browser session without going through UI login.

    Args:
        page: Playwright Page object
        token: JWT access token
    """
    page.evaluate(f"localStorage.setItem('auth_token', '{token}')")


# ============================================================================
# Project Setup Functions
# ============================================================================

def create_test_project(client: APIClient, name: str, description: str = "", token: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a test project via API.

    Args:
        client: APIClient instance
        name: Project name
        description: Project description (default: "")
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Project data response from API

    Raises:
        requests.HTTPError: If project creation fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.post(
                "/api/v1/projects/",
                json={
                    "name": name,
                    "description": description,
                    "color": "#3182CE"
                }
            )
        finally:
            client.token = original_token
    else:
        response = client.post(
            "/api/v1/projects/",
            json={
                "name": name,
                "description": description,
                "color": "#3182CE"
            }
        )

    return response


def get_test_projects(client: APIClient, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all test projects via API.

    Args:
        client: APIClient instance
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Projects data response from API

    Raises:
        requests.HTTPError: If request fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.get("/api/v1/projects/")
        finally:
            client.token = original_token
    else:
        response = client.get("/api/v1/projects/")

    return response


def delete_test_project(client: APIClient, project_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a test project via API.

    Note: This endpoint may not exist in the current implementation.
    Projects are typically stored in memory and cleared between test runs.

    Args:
        client: APIClient instance
        project_id: Project ID to delete
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Response data

    Raises:
        requests.HTTPError: If deletion fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.delete(f"/api/v1/projects/{project_id}")
        finally:
            client.token = original_token
    else:
        response = client.delete(f"/api/v1/projects/{project_id}")

    return response


# ============================================================================
# Skill Setup Functions
# ============================================================================

def install_test_skill(client: APIClient, skill_id: str, agent_id: str = "test-agent", token: Optional[str] = None) -> Dict[str, Any]:
    """
    Install a test skill via API.

    Args:
        client: APIClient instance
        skill_id: Skill ID to install
        agent_id: Agent ID that will use the skill (default: "test-agent")
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Installation response data

    Raises:
        requests.HTTPError: If installation fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.post(
                f"/marketplace/skills/{skill_id}/install",
                json={
                    "agent_id": agent_id,
                    "auto_install_deps": True
                }
            )
        finally:
            client.token = original_token
    else:
        response = client.post(
            f"/marketplace/skills/{skill_id}/install",
            json={
                "agent_id": agent_id,
                "auto_install_deps": True
            }
        )

    return response


def get_installed_skills(client: APIClient, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get installed skills via API.

    Note: This endpoint may need to be implemented.
    Currently, the marketplace provides search and installation endpoints.

    Args:
        client: APIClient instance
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Skills data response from API

    Raises:
        requests.HTTPError: If request fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            # Search all marketplace skills
            response = client.get("/marketplace/skills")
        finally:
            client.token = original_token
    else:
        response = client.get("/marketplace/skills")

    return response


def uninstall_test_skill(client: APIClient, skill_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Uninstall a test skill via API.

    Note: This endpoint may need to be implemented.
    Skills are typically managed through the skill adapter service.

    Args:
        client: APIClient instance
        skill_id: Skill ID to uninstall
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Response data

    Raises:
        requests.HTTPError: If uninstallation fails
    """
    # Note: Uninstall endpoint may not exist in current implementation
    # This is a placeholder for future implementation
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.delete(f"/marketplace/skills/{skill_id}")
        finally:
            client.token = original_token
    else:
        response = client.delete(f"/marketplace/skills/{skill_id}")

    return response
